#!/usr/bin/env python3

import argparse
import csv
import os
import json
import shutil
import subprocess
import pprint
import re
import sys
import time

from influxdb import InfluxDBClient

# TODO: add requests caching for dev

# TODO: reduce dependence on reading the devicepool config file somehow
#       - if we run a config different from what's checked in, we could have issues

# TODO: take path to git repo as arg, if passed don't clone/update a managed repo
#       - if running on devicepool host, we have the actual config being run... best thing to use.

try:
    import requests
    import yaml
    import pendulum
except ImportError:
    print("Missing dependencies. Please run `pipenv install; pipenv shell` and retry!")
    sys.exit(1)

REPO_UPDATE_SECONDS = 300
MAX_WORKER_TYPES = 50
MAX_WORKER_COUNT = 50
USER_AGENT_STRING = "Python (https://github.com/mozilla-platform-ops/android-tools/tree/master/worker_health)"
# for last started report: if no limit specified, still warn at this limit
ALERT_MINUTES = 60


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
            raise Exception("non-zero code returned")

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

        if self.verbosity > 1:
            print(an_url)
        response = requests.get(an_url, headers=headers)
        result = response.text
        output = json.loads(result)

        while "continuationToken" in output:
            payload = {"continuationToken": output["continuationToken"]}
            if self.verbosity > 1:
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

    # gets and sets the devices working in each queu
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
            if self.verbosity > 1:
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
                an_url = (
                    "https://queue.taskcluster.net/v1/task/%s/status"
                    % worker["latestTask"]["taskId"]
                )
                json_result2 = self.get_jsonc(an_url)
                if self.verbosity > 1:
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

    def show_last_started_report(self, limit=None):
        # TODO: show all queues, not just the ones with data

        base_string = "minutes since last TC job started"
        if limit:
            print(
                "%s (showing only those started more than %sm ago):"
                % (base_string, limit)
            )
        else:
            print(
                "%s (showing all workers, WARN at %sm):" % (base_string, ALERT_MINUTES)
            )

        for queue in self.devicepool_queues_and_workers:
            # check that there are jobs in this queue, if not continue
            if self.tc_queue_counts[queue] == 0:
                continue
            # TODO: if the queue isn't full, we can't expect all workers to be busy... mention that to user... don't warn?
            workers = len(self.devicepool_queues_and_workers[queue])
            jobs = self.tc_queue_counts[queue]
            print(
                "  %s (%s workers, %s jobs)"
                % (
                    queue,
                    workers,
                    jobs,
                )
            )
            if jobs <= workers:
                print("    results not displayed (unreliable as jobs <= workers)")
            else:
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

    def influx_logging_report(self, limit):
        # TODO: show all queues, not just the ones with data

        # TODO: get rid of intermittents
        # store a file with last_seen_online for each host
        #   - if not offline, remove
        #   - if offline, update timestamp in file
        #   - for alerting, see if last_seen_online exceeds threshold (2-5 minutes)

        missing_workers = []
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
                        missing_workers.append(worker)
                        mw2[queue].append(worker)
                        # print(
                        #     "    %s: %s: %s"
                        #     % (
                        #         worker,
                        #         self.tc_current_worker_last_started[worker],
                        #         difference,
                        #     )
                        # )
                else:
                    # fully missing wrker
                    # print("    %s: missing! (no data)" % worker)
                    missing_workers.append(worker)
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

    def write_multiline_influx_data(self, line_arr):
        db = "capacity_testing"

        client = InfluxDBClient(
            host="127.0.0.1",
            port=8086,
            ssl=False,
            verify_ssl=False,
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
        s = csv.reader(csv_string)
        return list(csv.reader([s]))[0]

    def get_offline_workers_from_journalctl(self):
        pattern = ": (.*) WARNING (.*) DISABLED (\d+) OFFLINE (\d+) (.*)"
        lines = self.get_journalctl_output()
        offline_dict = {}
        for line in lines:
                m = re.search(pattern, line)
                if m:
                    project = m.group(1)
                    queue = m.group(2)
                    disabled_count = m.group(3)
                    offline_count = m.group(4)
                    # TODO: un-csv this string
                    offline_hosts = m.group(5)
                    offline_dict[project] = self.csv_string_to_list(offline_hosts)
                    # print("%s: %s" % (project, offline_hosts))
                # m.group(0)
                # print(line)
                #pool =

        for k,v in offline_dict.items():
            print("%s: %s" % (k, v))


    def show_report(self, show_all=False, time_limit=None, influx_logging=False, verbosity=0):
        # TODO: handle queues that are present with 0 tasks
        # - have recently had jobs, but none currently and workers entries have dropped off/expired.
        # - solution: check count and only add if non-zero

        # from devicepool
        self.set_configured_worker_counts()

        # from queue.tc
        self.set_queue_counts()

        # from tc
        self.set_current_worker_types()
        self.set_current_workers()

        # testing
        #
        # self.pp.pprint(self.devicepool_queues_and_workers)
        # sys.exit()

        # display reports
        # self.calculate_utilization_and_dead_hosts(show_all)
        # print("")

        print("missing and tardy workers")
        if verbosity:
            print(
                "  from https://tools.taskcluster.net/provisioners/proj-autophone/worker-types"
            )
            print(
                "  config has %s projects/queues"
                % (len(self.devicepool_queues_and_workers))
            )
        # print("")

        self.show_last_started_report(time_limit)
        if time_limit:
            print("")
            missing_workers = self.influx_logging_report(time_limit)
            offline_workers = self.get_offline_workers_from_journalctl()
            print("summary: ")
            print(self.flatten_list(missing_workers.values()))
            print(self.flatten_list(offline_workers))
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
            self.write_multiline_influx_data(self.influx_log_lines_to_send)


def main():

    # TODO: catch ctrl-c and exit nicely

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        default=False,
        help="list all worker-types on TC even if not missing workers",
    )
    parser.add_argument(
        "-u",
        "--update",
        action="store_true",
        default=False,
        help="force an update to the devicepool repository (normally updated every %s seconds)"
        % REPO_UPDATE_SECONDS,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        dest="log_level",
        default=0,
        help="specify multiple times for even more verbosity",
    )
    parser.add_argument(
        "-t",
        "--time-limit",
        type=int,
        default=None,
        help="for last started report, only show devices that have started jobs longer than this many minutes ago",
    )
    parser.add_argument(
        "-i",
        "--influx-logging",
        action="store_true",
        default=False,
        help="testing: try to write missing_workers data to a local influx instance",
    )
    args = parser.parse_args()
    wh = WorkerHealth(args.log_level)

    # TESTING
    # output = wh.get_jsonc("https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types/gecko-t-ap-unit-p2/workers?limit=50")
    # wh.pp.pprint(output)
    # sys.exit(0)

    wh.show_report(args.all, args.time_limit, args.influx_logging, args.log_level)


if __name__ == "__main__":
    main()
