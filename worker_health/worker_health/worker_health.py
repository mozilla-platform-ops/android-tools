import csv
import getpass
import logging
import os
import re
import shutil
import subprocess
import sys
import time

import pendulum
import yaml

from . import utils

#
# DEPRECATED: see fitnenss.moonshot_worker_report
#

# log_format = '%(asctime)s %(levelname)-10s %(funcName)s: %(message)s'
log_format = "%(levelname)-10s %(funcName)s: %(message)s"
logging.basicConfig(format=log_format, stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger()


REPO_UPDATE_SECONDS = 300
MAX_WORKER_TYPES = 50
MAX_WORKER_COUNT = 50
USER_AGENT_STRING = "Python (https://github.com/mozilla-platform-ops/android-tools/tree/master/worker_health)"


class NonZeroExit(Exception):
    pass


# TODO: add requests caching for dev

# TODO: reduce dependence on reading the devicepool config file somehow
#       - if we run a config different from what's checked in, we could have issues

# TODO: take path to git repo as arg, if passed don't clone/update a managed repo
#       - if running on devicepool host, we have the actual config being run... best thing to use.


class WorkerHealth:
    def __init__(self, verbosity=0):
        username = getpass.getuser()
        self.devicepool_client_dir = os.path.join(
            "/", "tmp", ("worker_health.%s" % username), "mozilla-bitbar-devicepool"
        )
        self.devicepool_git_clone_url = (
            "https://github.com/mozilla-platform-ops/mozilla-bitbar-devicepool.git"
        )
        # self.pp = pprint.PrettyPrinter(indent=4)
        self.verbosity = verbosity
        #
        self.devicepool_config_yaml_path = None
        self.devicepool_config_yaml = None
        self.devicepool_bitbar_device_groups = {}
        # lists devices in each project
        # e.g. {'gecko-t-bitbar-gw-unit-p2': ['pixel2-11', 'pixel2-12'], ...}
        self.devicepool_project_to_tc_worker_type = {}
        # links device groups (in devicepool_bitbar_device_groups) to queues
        # e.g. {'mozilla-gw-unittest-p2': 'gecko-t-bitbar-gw-unit-p2', ...}
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

        if verbosity == 1:
            logger.setLevel(logging.INFO)
        if verbosity == 2:
            logger.setLevel(logging.DEBUG)

        # clone or update repo
        self.clone_or_update(self.devicepool_git_clone_url, self.devicepool_client_dir)
        # pick devicepool config file path
        self.set_devicepool_configuration_path()

    def run_cmd(self, cmd):
        return (
            subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
            .strip()
            .decode()
        )

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
                os.chdir("../..")
                try:
                    shutil.rmtree(repo_path)
                except OSError:
                    # if a file went away for some reason during this, fine...
                    pass
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

    def set_devicepool_configuration_path(self):
        # the path to the config in the devicepool repo checkout we make
        checkout_yaml_file_path = os.path.join(
            self.devicepool_client_dir, "config", "config.yml"
        )
        # this is that path that we expect the config file to be
        # at on a devicepool production host
        devicepool_host_yaml_file_path = (
            "/home/bitbar/mozilla-bitbar-devicepool/config/config.yml"
        )
        local_dev_path = os.path.join(
            os.path.expanduser("~"), "git/mozilla-bitbar-devicepool/config/config.yml"
        )
        if os.path.exists(local_dev_path):
            logger.warning(
                "Found devicepool config in local development location (not using repo checkout)!"
            )
            self.devicepool_config_yaml_path = local_dev_path
        elif os.path.exists(devicepool_host_yaml_file_path):
            logger.info(
                "Found devicepool config in production location (not using repo checkout)!"
            )
            self.devicepool_config_yaml_path = devicepool_host_yaml_file_path
        else:
            logger.debug(
                "Did NOT find devicepool config in production location. Using repo checkout."
            )
            self.devicepool_config_yaml_path = checkout_yaml_file_path

    def set_configured_worker_counts(self):
        yaml_file_path = self.devicepool_config_yaml_path
        with open(yaml_file_path, "r") as stream:
            try:
                self.devicepool_config_yaml = yaml.load(stream, Loader=yaml.Loader)
            except yaml.YAMLError as exc:
                print(exc)

        # get device group data
        for item in self.devicepool_config_yaml["device_groups"]:
            if (
                item.startswith("motog5")
                or item.startswith("pixel2")
                or item.startswith("pixel5")
                or item.startswith("s7")
                or item.startswith("a51")
                or item.startswith("test")
            ):
                if self.devicepool_config_yaml["device_groups"][item]:
                    keys = self.devicepool_config_yaml["device_groups"][item].keys()
                    self.devicepool_bitbar_device_groups[item] = list(keys)

        for project in self.devicepool_config_yaml["projects"]:
            if (
                project.endswith("p2")
                or project.endswith("p5")
                or project.endswith("g5")
                or project.endswith("a51")
                or project.endswith("s7")
                or "test" in project
            ):
                try:
                    # set the workers for a queue
                    self.devicepool_queues_and_workers[
                        self.devicepool_config_yaml["projects"][project][
                            "additional_parameters"
                        ]["TC_WORKER_TYPE"]
                    ] = self.devicepool_bitbar_device_groups[
                        self.devicepool_config_yaml["projects"][project][
                            "device_group_name"
                        ]
                    ]
                except KeyError:
                    # happens when no devicepool data for a queue
                    #   - when it's not being used
                    #     - like mozilla-gw-unittest-g5
                    pass
                # for linking dp project to tc worker type
                self.devicepool_project_to_tc_worker_type[
                    project
                ] = self.devicepool_config_yaml["projects"][project][
                    "additional_parameters"
                ][
                    "TC_WORKER_TYPE"
                ]

    # gets and sets the queues under proj-autophone
    def set_current_worker_types(self):
        # get the queues with data
        # https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types?limit=100
        url = (
            "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/provisioners/%s/worker-types/?limit=%s"
            # "https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types?limit=%s"
            % ("proj-autophone", MAX_WORKER_TYPES)
        )
        json_1 = utils.get_jsonc(url, self.verbosity)
        for item in json_1["workerTypes"]:
            self.tc_current_worker_types.append(item["workerType"])

    # gets and sets the devices working in each queue
    def set_current_workers(self):
        # get the workers and count of workers
        # https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types/gecko-t-ap-unit-p2/workers?limit=15
        for item in self.tc_current_worker_types:
            url = (
                "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/provisioners/%s/worker-types/%s/workers?limit=%s"
                # "https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types/%s/workers?limit=%s"
                % ("proj-autophone", item, MAX_WORKER_COUNT)
            )
            json_result = utils.get_jsonc(url, self.verbosity)
            if self.verbosity > 2:
                print("")
                print("%s (%s)" % (item, url))
                self.pp.pprint(json_result)

            retries_left = 2
            # tc can sometimes return empty results for this query, retry a few times
            while json_result["workers"] == []:
                json_result = utils.get_jsonc(url, self.verbosity)
                retries_left = retries_left - 1
                if retries_left == 0:
                    break

            # if json_result["workers"] == []:
            #     logger.warning(
            #         "no workers in %s... strange. let aerickson know if it continues"
            #         % item
            #     )
            #     logger.warning(url)

            self.tc_workers[item] = []
            for worker in json_result["workers"]:
                self.tc_workers[item].append(worker["workerId"])
                # TODO: quarantine data
                if "quarantineUntil" in worker:
                    self.quarantined_workers.append(worker["workerId"])
                if "latestTask" not in worker:
                    # worker has no lastesttask... brand new or tc restart?
                    # TODO: eventually alert if this persists
                    # print("worker %s has no latestTask" % worker["workerId"])
                    continue
                an_url = (
                    "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/%s/status"
                    # "https://queue.taskcluster.net/v1/task/%s/status"
                    % worker["latestTask"]["taskId"]
                )
                json_result2 = utils.get_jsonc(an_url, self.verbosity)
                if self.verbosity > 2:
                    print("%s result2: " % worker["workerId"])
                    self.pp.pprint(json_result2)

                # if a quarantined host's last job is old it will
                # expire and we can't look at it
                if "code" in json_result2:
                    if json_result2["code"] == "ResourceNotFound":
                        continue

                # look at the last record for the task, could be rescheduled
                strange_result = True
                try:
                    if "status" in json_result2:
                        if "runs" in json_result2["status"]:
                            # test pool workers, new workers
                            # - workers that just started won't have a 'started'
                            strange_result = False
                            # normal workers
                            # - set started_time if data
                            if "started" in json_result2["status"]["runs"][-1]:
                                started_time = json_result2["status"]["runs"][-1][
                                    "started"
                                ]
                                if (
                                    worker["workerId"]
                                    in self.tc_current_worker_last_started
                                ):
                                    if (
                                        self.tc_current_worker_last_started[
                                            worker["workerId"]
                                        ]
                                        < started_time
                                    ):
                                        self.tc_current_worker_last_started[
                                            worker["workerId"]
                                        ] = started_time
                                else:
                                    self.tc_current_worker_last_started[
                                        worker["workerId"]
                                    ] = started_time
                except KeyError:
                    # pass, because we mention the strange result below
                    pass

                if strange_result:
                    logger.warning(
                        "strange json_result2 for worker %s: %s"
                        % (worker["workerId"], json_result2)
                    )

    def show_last_started_report(self, limit=95, show_all=False, verbosity=0):
        # TODO: show all queues, not just the ones with data
        # TODO: now that we're defaulting limit, move limit mode to use verbosity.

        base_string = "tc: missing and tardy workers"
        if not show_all:
            print("%s, hosts started more than %sm ago" % (base_string, limit))
        else:
            print("%s, showing all workers" % base_string)

        if verbosity > 1:
            print(
                "  - from https://firefox-ci-tc.services.mozilla.com/provisioners/proj-autophone"
            )
            # print(
            #     "  - config has %s projects/queues"
            #     % (len(self.devicepool_queues_and_workers))
            # )

        for queue in self.devicepool_queues_and_workers:
            show_details = True
            workers = len(self.devicepool_queues_and_workers[queue])
            jobs = self.tc_queue_counts[queue]
            offline_or_tardy = []

            print("  %s (%s workers, %s jobs)" % (queue, workers, jobs))

            if jobs == 0:
                # don't show output, results are 100% unreliable
                show_details = False
            elif jobs <= workers:
                # unless we're -vv hide workers in this state
                if verbosity <= 1:
                    show_details = False

            if show_details:
                for worker in self.devicepool_queues_and_workers[queue]:
                    if worker in self.tc_current_worker_last_started:
                        if self.tc_current_worker_last_started[worker] is None:
                            print("    %s: present, no task start time!" % worker)
                            continue
                        now_dt = pendulum.now(tz="UTC")
                        last_started_dt = pendulum.parse(
                            self.tc_current_worker_last_started[worker]
                        )
                        difference = now_dt.diff(last_started_dt).in_minutes()

                        # display logic
                        display_host = False
                        if show_all:
                            display_host = True
                        if difference >= limit:
                            display_host = True
                            offline_or_tardy.append(worker)

                        # display host line
                        if display_host:
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
                        offline_or_tardy.append(worker)
                        # TODO: add this to missing!

            if offline_or_tardy and jobs <= workers:
                if verbosity > 1 or show_all:
                    print("    WARNING: results unreliable as jobs <= workers!")
                else:
                    print(
                        "    results not displayed (unreliable as jobs <= workers, -vv to show)"
                    )
                    show_details = False

    # calculate_missing_workers_from_tc doesn't care about time limits
    # - catches blind spot where devices are not in Bitbar system but are in our config
    #   - the output from self.calculate_missing_workers_from_tc misses these devices unless there are jobs in the queue
    #
    # new simpler function that doesn't worry about tardy
    def get_tc_missing_workers(self, verbose=False):

        missing_workers = set()
        expected_workers = self.get_devicepool_config_workers()
        for worker in expected_workers:
            if worker in self.tc_current_worker_last_started:
                pass
            else:
                if verbose:
                    print("boo  99 %s" % worker)
                missing_workers.add(worker)

        for queue in self.devicepool_queues_and_workers:
            if verbose:
                print(queue)
            # if the queue doesn't even appear under provisioner list, it's workers
            # aren't missing (there hasn't been work in a long time).
            # it's likely a test queue.
            if queue in self.tc_current_worker_types:
                pass
            else:
                if verbose:
                    print("removing workers from queue %s, as its not listed" % queue)
                missing_workers = set(missing_workers) - set(
                    self.devicepool_queues_and_workers[queue]
                )
                continue

            for worker in self.devicepool_queues_and_workers[queue]:
                if verbose:
                    print(worker)
                # # if no record of work, it's definitely missing
                if worker not in self.tc_current_worker_last_started:
                    if verbose:
                        print("boo adding %s 2" % worker)
                    missing_workers.add(worker)
                    continue

        # dedupe and return list
        return sorted(list(set(missing_workers)))

    # TODO: unit test this
    # rename/rework to detect_tardy()
    def calculate_missing_workers_from_tc(self, limit, exclude_quarantined=False):
        # TODO: get rid of intermittents
        # store a file with last_seen_online for each host
        #   - if not offline, remove
        #   - if offline, update timestamp in file
        #   - for alerting, see if last_seen_online exceeds threshold (2-5 minutes)

        mw2 = {}
        for queue in self.devicepool_queues_and_workers:
            mw2[queue] = []

            # queue-level flags used in decisions below
            #   - check that there are jobs in this queue, if not continue
            queue_empty = False
            if self.tc_queue_counts[queue] == 0:
                queue_empty = True
            #   - ensure # of jobs > # of workers
            #     - only case we're sure the device is having issues
            more_workers_than_jobs = False
            if self.tc_queue_counts[queue] < len(
                self.devicepool_queues_and_workers[queue]
            ):
                more_workers_than_jobs = True

            for worker in self.devicepool_queues_and_workers[queue]:
                if not exclude_quarantined and worker in self.quarantined_workers:
                    mw2[queue].append(worker)
                    continue

                if worker in self.tc_current_worker_last_started:
                    # new workers
                    if self.tc_current_worker_last_started[worker] is None:
                        # TODO: track these in a new datastructure
                        #   - not a 'problem worker' per se
                        #     - shouldn't alert partners or logging, but good to know
                        continue
                    if queue_empty:
                        continue
                    if more_workers_than_jobs:
                        continue
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
                    if queue_empty:
                        continue
                    if more_workers_than_jobs:
                        continue
                    # fully missing worker
                    mw2[queue].append(worker)
        return mw2

    def gen_influx_mw_lines(self, queue_to_worker_map, provisioner="proj-autophone"):
        lines = []
        for queue in queue_to_worker_map:
            worker_count = len(queue_to_worker_map[queue])
            lines.append(
                "bitbar_workers,provisioner=%s,queue=%s problem=%s"
                % (provisioner, queue, worker_count)
            )
        return lines

    def gen_influx_cw_lines(self, missing, provisioner="proj-autophone"):
        lines = []
        for queue in missing:
            lines.append(
                "bitbar_workers,provisioner=%s,queue=%s configured=%s"
                % (provisioner, queue, len(missing[queue]))
            )
        return lines

    def set_queue_counts(self):
        for queue in self.devicepool_queues_and_workers:
            an_url = (
                "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/pending/%s/%s"
                # "https://queue.taskcluster.net/v1/pending/proj-autophone/%s"
                % ("proj-autophone", queue)
            )
            json_result = utils.get_jsonc(an_url, self.verbosity)
            if "pendingTasks" in json_result:
                self.tc_queue_counts[queue] = json_result["pendingTasks"]
            else:
                logger.warning("failed to get counts for queue '%s'", queue)

    def flatten_list(self, list_to_flatten, sort_output=True):
        flattened_list = []

        # if empty list passed, return quickly
        if not list_to_flatten:
            return flattened_list

        # flatten the list
        for x in list_to_flatten:
            for y in x:
                flattened_list.append(y)

        if sort_output:
            flattened_list.sort()

        return flattened_list

    def make_list_unique(self, list_input):
        # python 2 uses Set (vs set)
        n_set = set(list_input)
        output = list(n_set)
        output.sort()
        return output

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
        if not utils.bitbar_systemd_service_present():
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
                project = m.group(1).strip()
                device_group_name = self.devicepool_project_to_tc_worker_type[project]
                # queue = m.group(2)
                # disabled_count = m.group(3)
                # offline_count = m.group(4)
                offline_hosts = m.group(5)
                offline_dict[device_group_name] = self.csv_string_to_list(offline_hosts)

        # for k,v in offline_dict.items():
        #     print("%s: %s" % (k, v))

        return offline_dict

    # gathers and generates data
    # TODO: run in init
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

    def get_devicepool_config_workers(self):
        yaml_file_path = self.devicepool_config_yaml_path
        # TODO:  pull this out and only do once
        with open(yaml_file_path, "r") as stream:
            try:
                self.devicepool_config_yaml = yaml.load(stream, Loader=yaml.Loader)
            except yaml.YAMLError as exc:
                print(exc)

        return_arr = []

        for item in self.devicepool_config_yaml["device_groups"]:
            if (
                item.startswith("motog5")
                or item.startswith("pixel2")
                or item.startswith("pixel5")
                or item.startswith("a51")
                or item.startswith("s7")
                or item.startswith("test")
            ):
                # print(item)
                if self.devicepool_config_yaml["device_groups"][item]:
                    devices = list(self.devicepool_config_yaml["device_groups"][item])
                    # print("  %s" % devices)
                    return_arr.extend(devices)

        return set(return_arr)

    # returns a dict
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

    def show_missing_workers_report(self, show_all=False, time_limit=None, verbosity=0):
        self.gather_data()

        if verbosity:
            self.show_last_started_report(
                limit=time_limit, show_all=show_all, verbosity=verbosity
            )
            print("")

        missing_workers = {}
        missing_workers_flattened = []
        offline_workers = {}
        offline_workers_flattened = []

        if time_limit:
            output_format = "%-16s %s"

            # exclude quarantined as we mention them specifically later
            missing_workers = self.calculate_missing_workers_from_tc(
                time_limit, exclude_quarantined=True
            )
            missing_workers_flattened = self.flatten_list(missing_workers.values())
            print(
                output_format
                % (
                    "tc (%s)" % len(missing_workers_flattened),
                    missing_workers_flattened,
                )
            )

            mw2 = self.get_tc_missing_workers()
            print(
                output_format
                % (
                    "tc 2 (%s)" % len(mw2),
                    mw2,
                )
            )

            if self.quarantined_workers:
                print(
                    output_format
                    % (
                        "tc-quarantined (%s)" % len(self.quarantined_workers),
                        self.quarantined_workers,
                    )
                )

            if utils.bitbar_systemd_service_present():
                offline_workers = self.get_offline_workers_from_journalctl()
                offline_workers_flattened = self.flatten_list(offline_workers.values())
                print(
                    output_format
                    % (
                        "devicepool (%s)" % len(offline_workers_flattened),
                        offline_workers_flattened,
                    )
                )

                merged = self.make_list_unique(
                    offline_workers_flattened + missing_workers_flattened
                )

                print(output_format % ("union (%s)" % len(merged), merged))

                intersection_list = utils.list_intersection(
                    offline_workers_flattened, missing_workers_flattened
                )

                print(
                    output_format
                    % ("intersection (%s)" % len(intersection_list), intersection_list)
                )

    # devicepool specific
    def get_slack_report(self, show_all=False, time_limit=None, verbosity=0):
        self.gather_data()

        missing_workers = {}
        missing_workers_flattened = []
        offline_workers = {}
        offline_workers_flattened = []

        result_dict = {"tc": [], "devicepool": [], "union": [], "intersection": []}

        if time_limit:
            # exclude quarantined as we mention them specifically later
            missing_workers = self.calculate_missing_workers_from_tc(
                time_limit, exclude_quarantined=True
            )
            missing_workers_flattened = self.flatten_list(missing_workers.values())
            result_dict["tc"] = missing_workers_flattened

            # TODO: do quarantined
            # if self.quarantined_workers:
            #     print(
            #         output_format
            #         % (
            #             "tc-quarantined (%s)" % len(self.quarantined_workers),
            #             self.quarantined_workers,
            #         )
            #     )

            if utils.bitbar_systemd_service_present():
                offline_workers = self.get_offline_workers_from_journalctl()
                offline_workers_flattened = self.flatten_list(offline_workers.values())
                result_dict["devicepool"] = offline_workers_flattened

            result_dict["union"] = self.make_list_unique(
                offline_workers_flattened + missing_workers_flattened
            )

            result_dict["intersection"] = utils.list_intersection(
                offline_workers_flattened, missing_workers_flattened
            )

            return result_dict

    def influx_report(self, time_limit=None, verbosity=0):
        problem_workers = self.get_problem_workers2(
            time_limit=time_limit, exclude_quarantined=False
        )

        logger.info("generating influx log lines for problem workers...")
        self.influx_log_lines_to_send.extend(self.gen_influx_mw_lines(problem_workers))

        logger.info("generating influx log lines for configured workers...")
        self.influx_log_lines_to_send.extend(
            self.gen_influx_cw_lines(self.devicepool_queues_and_workers)
        )

        # return so caller can display
        return problem_workers


if __name__ == "__main__":
    wh = WorkerHealth()

    wh.gather_data()

    # print(wh.get_devicepool_config_workers())
    # print(wh.devicepool_queues_and_workers)

    import pprint

    pprint.pprint(wh.tc_current_worker_last_started)

    print(wh.get_tc_missing_workers())

    # print()
    # print(wh.devicepool_queues_and_workers)
