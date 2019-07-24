import csv
import json
import logging
import os
import pprint
import re
import shutil
import subprocess
import sys
import time

# log_format = '%(asctime)s %(levelname)-10s %(funcName)s: %(message)s'
log_format = "%(levelname)-10s %(funcName)s: %(message)s"
logging.basicConfig(format=log_format, stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger()

try:
    from influxdb import InfluxDBClient
    import pendulum
    import requests
    import yaml
except ImportError:
    print("Missing dependencies. Please run `pipenv install; pipenv shell` and retry!")
    sys.exit(1)

REPO_UPDATE_SECONDS = 300
MAX_WORKER_TYPES = 50
MAX_WORKER_COUNT = 50
USER_AGENT_STRING = "Python (https://github.com/mozilla-platform-ops/android-tools/tree/master/worker_health)"
# for last started report: if no limit specified, still warn at this limit
ALERT_MINUTES = 60


class NonZeroExit(Exception):
    pass


# TODO: add requests caching for dev

# TODO: reduce dependence on reading the devicepool config file somehow
#       - if we run a config different from what's checked in, we could have issues

# TODO: take path to git repo as arg, if passed don't clone/update a managed repo
#       - if running on devicepool host, we have the actual config being run... best thing to use.


class WorkerHealth:
    def __init__(self, verbosity=0):
        self.devicepool_client_dir = os.path.join(
            "/", "tmp", "worker_health", "mozilla-bitbar-devicepool"
        )
        self.devicepool_git_clone_url = (
            "https://github.com/bclary/mozilla-bitbar-devicepool.git"
        )
        self.pp = pprint.PrettyPrinter(indent=4)
        self.verbosity = verbosity
        #
        self.devicepool_config_yaml = None
        self.devicepool_bitbar_device_groups = {}
        self.devicepool_project_to_device_group_name = {}
        # links device groups (in devicepool_bitbar_device_groups) to queues
        self.devicepool_queues_and_workers = {}
        # just the current queue names
        self.tc_queue_counts = {}
        self.tc_current_worker_types = []
        self.tc_current_worker_last_started = {}
        self.tc_current_worker_last_resolved = {}
        # similar to devicepool_bitbar_device_groups
        self.tc_workers = {}

        self.influx_log_lines_to_send = []
        # TODO: store these
        self.problem_workers = {}
        self.quarantined_workers = []

        # clone or update repo
        self.clone_or_update(self.devicepool_git_clone_url, self.devicepool_client_dir)

    def run_cmd(self, cmd):
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        proc.wait(timeout=10)
        rc = proc.returncode
        if rc == 0:
            tmp = proc.stdout.read().strip()
            return tmp.decode()
        else:
            raise NonZeroExit("non-zero code returned")

    def clone_or_update(self, repo_url, repo_path, force_update=False):
        devnull_fh = open(os.devnull, "w")
        last_updated_file = os.path.join(
            repo_path, ".git", "missing_workers_last_updated"
        )

        if os.path.exists(repo_path):
            # return if it hasn't been long enough and force_update is false
            now = time.time()
            statbuf = os.stat(last_updated_file)
            mod_time = statbuf.st_mtime
            diff = now - mod_time
            if not force_update and diff < REPO_UPDATE_SECONDS:
                return

            os.chdir(repo_path)
            # reset
            cmd = "git reset --hard"
            args = cmd.split(" ")
            subprocess.check_call(args, stdout=devnull_fh, stderr=subprocess.STDOUT)

            # update
            cmd = "git pull --rebase"
            args = cmd.split(" ")
            try:
                subprocess.check_call(args, stdout=devnull_fh, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError:
                # os x has whacked the repo, reclone
                os.chdir("..")
                shutil.rmtree(repo_path)
                cmd = "git clone %s %s" % (repo_url, repo_path)
                args = cmd.split(" ")
                subprocess.check_call(args, stdout=devnull_fh, stderr=subprocess.STDOUT)
        else:
            # clone
            cmd = "git clone %s %s" % (repo_url, repo_path)
            args = cmd.split(" ")
            subprocess.check_call(args, stdout=devnull_fh, stderr=subprocess.STDOUT)
        # touch the last updated file
        open(last_updated_file, "a").close()
        os.utime(last_updated_file, None)

    # handles continuationToken
    def get_jsonc(self, an_url):
        headers = {"User-Agent": USER_AGENT_STRING}

        if self.verbosity > 2:
            print(an_url)
        response = requests.get(an_url, headers=headers)
        result = response.text
        output = json.loads(result)

        while "continuationToken" in output:
            payload = {"continuationToken": output["continuationToken"]}
            if self.verbosity > 2:
                print("%s, %s" % (an_url, output["continuationToken"]))
            response = requests.get(an_url, headers=headers, params=payload)
            result = response.text
            output = json.loads(result)
        return output

    def set_configured_worker_counts(self):
        yaml_file_path = os.path.join(
            self.devicepool_client_dir, "config", "config.yml"
        )
        with open(yaml_file_path, "r") as stream:
            try:
                self.devicepool_config_yaml = yaml.load(stream, Loader=yaml.Loader)
            except yaml.YAMLError as exc:
                print(exc)

        # get device group data
        for item in self.devicepool_config_yaml["device_groups"]:
            if item.startswith("motog5") or item.startswith("pixel2"):
                if self.devicepool_config_yaml["device_groups"][item]:
                    keys = self.devicepool_config_yaml["device_groups"][item].keys()
                    self.devicepool_bitbar_device_groups[item] = list(keys)

        # link device group data with queue names
        for project in self.devicepool_config_yaml["projects"]:
            if project.endswith("p2") or project.endswith("g5"):
                try:
                    self.devicepool_queues_and_workers[
                        self.devicepool_config_yaml["projects"][project][
                            "additional_parameters"
                        ]["TC_WORKER_TYPE"]
                    ] = self.devicepool_bitbar_device_groups[
                        self.devicepool_config_yaml["projects"][project][
                            "device_group_name"
                        ]
                    ]
                    self.devicepool_project_to_device_group_name[
                        project
                    ] = self.devicepool_config_yaml["projects"][project][
                        "device_group_name"
                    ]
                except KeyError:
                    pass

    # gets and sets the queues under proj-autophone
    def set_current_worker_types(self):
        # get the queues with data
        # https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types?limit=100
        url = (
            "https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types?limit=%s"
            % MAX_WORKER_TYPES
        )
        json_1 = self.get_jsonc(url)
        for item in json_1["workerTypes"]:
            self.tc_current_worker_types.append(item["workerType"])

    # gets and sets the devices working in each queue
    def set_current_workers(self):
        # get the workers and count of workers
        # https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types/gecko-t-ap-unit-p2/workers?limit=15
        pass

        for item in self.tc_current_worker_types:
            # if count is zero for queue, skip (otherwise we'll infinitely loop below in while block)
            if self.tc_queue_counts[item] == 0:
                continue

            url = (
                "https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types/%s/workers?limit=%s"
                % (item, MAX_WORKER_COUNT)
            )
            json_result = self.get_jsonc(url)
            if self.verbosity > 2:
                print("")
                print("%s (%s)" % (item, url))
                self.pp.pprint(json_result)
            # lol, gross, but works... we should never get a queue that has 0 workers here.
            # TODO: only retry 3 times or something
            while json_result["workers"] == []:
                json_result = self.get_jsonc(url)

            self.tc_workers[item] = []
            for worker in json_result["workers"]:
                self.tc_workers[item].append(worker["workerId"])
                # TODO: quarantine data
                if "quarantineUntil" in worker:
                    self.quarantined_workers.append(worker["workerId"])
                an_url = (
                    "https://queue.taskcluster.net/v1/task/%s/status"
                    % worker["latestTask"]["taskId"]
                )
                json_result2 = self.get_jsonc(an_url)
                if self.verbosity > 2:
                    print("%s result2: " % worker["workerId"])
                    self.pp.pprint(json_result2)
                # look at the last record for the task, could be rescheduled
                if "started" in json_result2["status"]["runs"][-1]:
                    started_time = json_result2["status"]["runs"][-1]["started"]
                    self.tc_current_worker_last_started[
                        worker["workerId"]
                    ] = started_time
                else:
                    # TODO: for debugging, print json
                    pass

    def calculate_utilization_and_dead_hosts(self, show_all=False):
        difference_found = False
        print("missing workers (present in config, but not on tc):")
        for item in self.devicepool_queues_and_workers:
            # wh.tc_workers
            if show_all:
                print("  %s (%s jobs): " % (item, self.tc_queue_counts[item]))
                print(
                    "    https://tools.taskcluster.net/provisioners/proj-autophone/worker-types/%s"
                    % item
                )
                if item in self.devicepool_queues_and_workers:
                    print(
                        "    devicepool: %s" % self.devicepool_queues_and_workers[item]
                    )
                if item in self.tc_workers:
                    print("    taskcluster: %s" % self.tc_workers[item])
            if item in self.devicepool_queues_and_workers and item in self.tc_workers:
                difference = set(self.devicepool_queues_and_workers[item]) - set(
                    self.tc_workers[item]
                )
                if show_all:
                    if difference:
                        difference_found = True
                        print("    difference: %s" % sorted(difference))
                    else:
                        print("    difference: none")
                else:
                    if difference:
                        difference_found = True
                        print("  %s (%s jobs): " % (item, self.tc_queue_counts[item]))
                        print(
                            "    https://tools.taskcluster.net/provisioners/proj-autophone/worker-types/%s"
                            % item
                        )
                        print("    difference: %s" % sorted(difference))

        if not difference_found and not show_all:
            print("  differences: none")
            print(
                "    https://tools.taskcluster.net/provisioners/proj-autophone/worker-types"
            )

    def show_last_started_report(self, limit=None, verbosity=0):
        # TODO: show all queues, not just the ones with data
        # TODO: now that we're defaulting limit, move limit mode to use verbosity.

        base_string = "tc: missing and tardy workers,"
        if limit:
            print("%s hosts started more than %sm ago" % (base_string, limit))
        else:
            print("%s showing all workers, WARN at %sm" % (base_string, ALERT_MINUTES))

        if verbosity > 1:
            print(
                "  - from https://tools.taskcluster.net/provisioners/proj-autophone/worker-types"
            )
            print(
                "  - config has %s projects/queues"
                % (len(self.devicepool_queues_and_workers))
            )

        for queue in self.devicepool_queues_and_workers:
            show_details = True
            workers = len(self.devicepool_queues_and_workers[queue])
            jobs = self.tc_queue_counts[queue]

            print("  %s (%s workers, %s jobs)" % (queue, workers, jobs))

            if jobs == 0:
                show_details = False
            elif jobs <= workers:
                if verbosity > 1:
                    print("    WARNING: results unreliable as jobs <= workers!")
                else:
                    print("    results not displayed (unreliable as jobs <= workers)")
                    show_details = False

            if show_details:
                for worker in self.devicepool_queues_and_workers[queue]:
                    if worker in self.tc_current_worker_last_started:
                        now_dt = pendulum.now(tz="UTC")
                        last_started_dt = pendulum.parse(
                            self.tc_current_worker_last_started[worker]
                        )
                        difference = now_dt.diff(last_started_dt).in_minutes()
                        if not limit:
                            # even though no limit, indicate when we think a worker is bad
                            if difference >= ALERT_MINUTES:
                                print(
                                    "    %s: %s: %s (WARN)"
                                    % (
                                        worker,
                                        self.tc_current_worker_last_started[worker],
                                        difference,
                                    )
                                )
                            else:
                                print(
                                    "    %s: %s: %s"
                                    % (
                                        worker,
                                        self.tc_current_worker_last_started[worker],
                                        difference,
                                    )
                                )
                        else:
                            if difference >= limit:
                                print(
                                    "    %s: %s: %s"
                                    % (
                                        worker,
                                        self.tc_current_worker_last_started[worker],
                                        difference,
                                    )
                                )
                    else:
                        print("    %s: missing! (no data)" % worker)
                        # TODO: add this to missing!

    def calculate_missing_workers_from_tc(self, limit, exclude_quarantined=False):
        # TODO: get rid of intermittents
        # store a file with last_seen_online for each host
        #   - if not offline, remove
        #   - if offline, update timestamp in file
        #   - for alerting, see if last_seen_online exceeds threshold (2-5 minutes)

        mw2 = {}
        for queue in self.devicepool_queues_and_workers:
            mw2[queue] = []
            # check that there are jobs in this queue, if not continue
            if self.tc_queue_counts[queue] == 0:
                continue
            # ensure # of jobs > # of workers, otherwise we're not 100% sure the device is having issues
            if self.tc_queue_counts[queue] < len(
                self.devicepool_queues_and_workers[queue]
            ):
                continue
            for worker in self.devicepool_queues_and_workers[queue]:
                if worker in self.tc_current_worker_last_started:
                    # tardy workers
                    now_dt = pendulum.now(tz="UTC")
                    last_started_dt = pendulum.parse(
                        self.tc_current_worker_last_started[worker]
                    )
                    difference = now_dt.diff(last_started_dt).in_minutes()
                    if difference >= limit:
                        if exclude_quarantined and worker in self.quarantined_workers:
                            continue
                        mw2[queue].append(worker)
                else:
                    # fully missing worker
                    # - devicepool lists these as offline
                    if exclude_quarantined and worker in self.quarantined_workers:
                        continue
                    mw2[queue].append(worker)
        return mw2

    def gen_influx_mw_lines(self, queue_to_worker_map, provisioner="proj-autophone"):
        lines = []
        for queue in queue_to_worker_map:
            worker_count = len(queue_to_worker_map[queue])
            lines.append(
                "workers,provisioner=%s,queue=%s missing=%s"
                % (provisioner, queue, worker_count)
            )
        return lines

    def gen_influx_cw_lines(self, missing, provisioner="proj-autophone"):
        lines = []
        for queue in missing:
            lines.append(
                "workers,provisioner=%s,queue=%s configured=%s"
                % (provisioner, queue, len(missing[queue]))
            )
        return lines

    def write_multiline_influx_data_locally(self, line_arr):
        db = "capacity_testing"

        client = InfluxDBClient(
            host="127.0.0.1", port=8086, ssl=False, verify_ssl=False
        )

        client.write(line_arr, {"db": db}, 204, "line")

    def set_queue_counts(self):
        for queue in self.devicepool_queues_and_workers:
            an_url = (
                "https://queue.taskcluster.net/v1/pending/proj-autophone/%s" % queue
            )
            json_result = self.get_jsonc(an_url)
            self.tc_queue_counts[queue] = json_result["pendingTasks"]

    def flatten_list(self, list_to_flatten):
        flattened_list = []

        # if empty list passed, return quickly
        if not list_to_flatten:
            return flattened_list

        # flatten the list
        for x in list_to_flatten:
            for y in x:
                flattened_list.append(y)
        return flattened_list

    def make_list_unique(self, list_input):
        # python 2 uses Set (vs set)
        n_set = set(list_input)
        return list(n_set)

    # sorts also!
    def dict_merge_with_dedupe(self, dict1, dict2):
        for key, value in dict1.items():
            if key not in dict2:
                dict2[key] = []
            dict2[key].extend(value)
            dict2[key] = self.make_list_unique(dict2[key])
            dict2[key].sort()
        return dict2

    # preserves dupes
    def dict_merge(self, dict1, dict2):
        for key, value in dict1.items():
            dict2[key].extend(value)
        return dict2

    def flatten_dict(self, a_dict):
        flattened = self.flatten_list(a_dict.values())
        flattened = self.make_list_unique(flattened)
        flattened.sort()
        return flattened

    def get_journalctl_output(self):
        MINUTES_OF_LOGS_TO_INSPECT = 5

        # NOTE: user running needs to be in adm group to not need sudo
        cmd = (
            "journalctl -u bitbar --since '%s minutes ago'" % MINUTES_OF_LOGS_TO_INSPECT
        )
        try:
            res = self.run_cmd(cmd)
        except subprocess.TimeoutExpired:
            # just try again for now... should work this time
            # if not, explode and let systemd restart
            res = self.run_cmd(cmd)
        lines = res.split("\n")
        # output = len(lines)
        # TODO: check res?
        return lines

    def csv_string_to_list(self, csv_string):
        return list(csv.reader([csv_string], skipinitialspace=True))[0]

    def get_offline_workers_from_journalctl(self):
        if not self.bitbar_systemd_service_present():
            logger.debug("bitbar systemd service not present, returning early.")
            return {}
        pattern = r": (.*) WARNING (.*) DISABLED (\d+) OFFLINE (\d+) (.*)"
        lines = self.get_journalctl_output()
        offline_dict = {}
        for line in lines:
            m = re.search(pattern, line)
            if m:
                # TODO: use worker type as key vs project
                # - gecko-t-bitbar-gw-perf-p2
                project = m.group(1)
                device_group_name = self.devicepool_project_to_device_group_name[
                    project
                ]
                # queue = m.group(2)
                # disabled_count = m.group(3)
                # offline_count = m.group(4)
                offline_hosts = m.group(5)
                offline_dict[device_group_name] = self.csv_string_to_list(offline_hosts)

        # for k,v in offline_dict.items():
        #     print("%s: %s" % (k, v))

        return offline_dict

    def bitbar_systemd_service_present(self, warn=False, error=False):
        try:
            self.run_cmd("systemctl status bitbar > /dev/null 2>&1")
        except NonZeroExit:
            if warn:
                logger.warn(
                    "this should be run on the primary devicepool host for maximum data."
                )
            if error:
                logger.error(
                    "this must be run on the primary devicepool host!"
                )
            return False
        return True

    # gathers and generates data
    def gather_data(self):
        # from devicepool
        self.set_configured_worker_counts()
        # from queue.tc
        self.set_queue_counts()
        # from tc
        self.set_current_worker_types()
        self.set_current_workers()
        # TODO: write these two
        # - missing and offline separate?
        # self.set_problem_workers()
        # self.set_configured_workers()

  # merged taskcluster tardy and devicepool offline data to one list
    # TODO: add taskcluster missing data
    def get_problem_workers(
        self, time_limit=None, verbosity=0, exclude_quarantined=False
    ):
        self.gather_data()

        # testing
        #
        # self.pp.pprint(self.devicepool_queues_and_workers)
        # sys.exit()

        # display reports
        # self.calculate_utilization_and_dead_hosts(show_all)
        # print("")

        missing_workers = {}
        missing_workers_flattened = []
        offline_workers = {}
        offline_workers_flattened = []

        missing_workers = self.calculate_missing_workers_from_tc(
            time_limit, exclude_quarantined=exclude_quarantined
        )
        missing_workers_flattened = self.flatten_list(missing_workers.values())
        missing_workers_flattened.sort()
        # print("tc: %s" % missing_workers_flattened)
        offline_workers = self.get_offline_workers_from_journalctl()
        offline_workers_flattened = self.flatten_list(offline_workers.values())
        offline_workers_flattened.sort()
        # print("dp: %s" % offline_workers_flattened)
        # TODO: calculate merged

        merged = self.make_list_unique(
            offline_workers_flattened + missing_workers_flattened
        )
        merged.sort()

        # print("merged: %s" % merged)
        return merged

    # returns a dict vs list
    def get_problem_workers2(
        self, time_limit=None, verbosity=0, exclude_quarantined=False
    ):
        # TODO: stop calling gather_data in processing/calculation code
        # - only call when necessary, push up to higher level
        self.gather_data()

        missing_workers = self.calculate_missing_workers_from_tc(
            time_limit, exclude_quarantined=exclude_quarantined
        )
        offline_workers = self.get_offline_workers_from_journalctl()

        merged2 = self.dict_merge_with_dedupe(missing_workers, offline_workers)

        # print("quarantined: %s" % self.quarantined_workers)
        # print("missing: %s" % missing_workers)
        # print("offline: %s" % offline_workers)
        # print("")
        # print("merged2: %s" % merged2)

        # use flatten_dict if needed in list
        return merged2

    def show_report(
        self, show_all=False, time_limit=None, influx_logging=False, verbosity=0
    ):
        # TODO: handle queues that are present with 0 tasks
        # - have recently had jobs, but none currently and workers entries have dropped off/expired.
        # - solution: check count and only add if non-zero

        self.gather_data()

        # testing
        #
        # self.pp.pprint(self.devicepool_queues_and_workers)
        # sys.exit()

        # display reports
        # self.calculate_utilization_and_dead_hosts(show_all)
        # print("")

        if verbosity:
            self.show_last_started_report(time_limit, verbosity)
            print("")

        missing_workers = {}
        missing_workers_flattened = []
        offline_workers = {}
        offline_workers_flattened = []

        if time_limit:
            output_format = "%-07s %s"

            missing_workers = self.calculate_missing_workers_from_tc(time_limit)
            missing_workers_flattened = self.flatten_list(missing_workers.values())
            missing_workers_flattened.sort()
            print(output_format % ("tc", missing_workers_flattened))
            if self.bitbar_systemd_service_present():
                offline_workers = self.get_offline_workers_from_journalctl()
                offline_workers_flattened = self.flatten_list(offline_workers.values())
                offline_workers_flattened.sort()
                print(output_format % ("dp", offline_workers_flattened))

                merged = self.make_list_unique(
                    offline_workers_flattened + missing_workers_flattened
                )
                merged.sort()

                print(output_format % ("merged", merged))
            if influx_logging:
                self.influx_log_lines_to_send.extend(
                    self.gen_influx_mw_lines(missing_workers)
                )
        if influx_logging:
            pass
            # TODO: ideally only log this every 1 hour?
            self.influx_log_lines_to_send.extend(
                self.gen_influx_cw_lines(self.devicepool_queues_and_workers)
            )
        if influx_logging:
            self.write_multiline_influx_data_locally(self.influx_log_lines_to_send)

    def influx_report(self, time_limit=None, verbosity=0):
        self.gather_data()

        missing_workers = self.calculate_missing_workers_from_tc(time_limit)
        offline_workers = self.get_offline_workers_from_journalctl()
        problem_workers = self.dict_merge_with_dedupe(missing_workers, offline_workers)

        self.influx_log_lines_to_send.extend(self.gen_influx_mw_lines(problem_workers))

        self.influx_log_lines_to_send.extend(
            self.gen_influx_cw_lines(self.devicepool_queues_and_workers)
        )
