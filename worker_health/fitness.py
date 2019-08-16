#!/usr/bin/env python3

import argparse
import json
import pprint
import sys
from multiprocessing.pool import ThreadPool
from time import time as timer
from urllib.request import urlopen

import requests

from worker_health import USER_AGENT_STRING, logger

# for each queue
#   for each worker
#     for each job listed in https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types/gecko-t-bitbar-gw-unit-p2/workers/bitbar/pixel2-05
#        check result in https://queue.taskcluster.net/v1/task/N8aF_LpZTWO7B1iGbKy3Yw

WORKERTYPE_THREAD_COUNT = 4
TASK_THREAD_COUNT = 6
ALERT_PERCENT = 0.85
DEFAULT_PROVISIONER = "proj-autophone"


class Fitness:
    def __init__(
        self,
        log_level=0,
        provisioner=DEFAULT_PROVISIONER,
        alert_percent=ALERT_PERCENT,
        testing_mode=False,
    ):
        self.verbosity = log_level
        self.alert_percent = alert_percent
        self.provisioner = provisioner

    def get_worker_jobs(self, queue, worker_type, worker):
        return self.get_jsonc(
            # TODO: need to get worker-group...
            "https://queue.taskcluster.net/v1/provisioners/%s/worker-types/%s/workers/%s/%s"
            % (self.provisioner, queue, worker_type, worker)
        )

    def get_task_status(self, taskid):
        _url, output, exception = self.get_jsonc2(
            "https://queue.taskcluster.net/v1/task/%s/status" % taskid
        )
        return taskid, output, exception

    def format_workertype_fitness_report_result(self, res):
        worker_id = res["worker_id"]
        del res["worker_id"]
        return "%s: %s" % (worker_id, res)

    def main(self, provisioner, worker_type, worker_id):
        start = timer()
        if worker_type and worker_id:
            ## host mode
            # TODO: get workr_group
            url = (
                "https://queue.taskcluster.net/v1/provisioners/%s/worker-types/%s/workers?limit=5"
                % (self.provisioner, worker_type)
            )
            # print(url)
            worker_group_result = self.get_jsonc(url)
            # worker_group = worker_group_result['workerTypes'][0][]
            # import pprint
            # pprint.pprint(worker_group_result)
            # sys.exit()
            worker_group = worker_group_result["workers"][0]["workerGroup"]
            _worker, res_obj, _e = self.device_fitness_report(
                worker_type, worker_group, worker_id
            )
            print("%s.%s: %s" % (worker_type, worker_id, res_obj))
        elif worker_type:
            ### queue mode
            _wt, res_obj, e = self.workertype_fitness_report(worker_type)
            for item in res_obj:
                # print(item)
                print(
                    "%s.%s"
                    % (worker_type, self.format_workertype_fitness_report_result(item))
                )
        else:
            ### provisioner mode
            worker_types_result = self.get_worker_types(provisioner)
            worker_types = []
            for provisioner in worker_types_result["workerTypes"]:
                worker_type = provisioner["workerType"]
                worker_types.append(worker_type)
            # print(worker_types)

            for worker_type in worker_types:
                # copied from block above
                wt, res_obj, e = self.workertype_fitness_report(worker_type)
                for item in res_obj:
                    print(
                        "%s.%s"
                        % (wt, self.format_workertype_fitness_report_result(item))
                    )
        print("Elapsed Time: %s" % (timer() - start,))

    # for provisioner report...
    def get_worker_types(self, provisioner):
        # https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types?limit=100
        return self.get_jsonc(
            "https://queue.taskcluster.net/v1/provisioners/%s/worker-types?limit=100"
            % provisioner
        )

    def workertype_fitness_report(self, worker_type):
        url = (
            "https://queue.taskcluster.net/v1/provisioners/%s/worker-types/%s/workers?limit=100"
            % (self.provisioner, worker_type)
        )
        # print(url)
        workers_result = self.get_jsonc(url)

        worker_ids = []
        for worker in workers_result["workers"]:
            worker_id = worker["workerId"]
            worker_group = worker["workerGroup"]
            worker_ids.append((worker_type, worker_group, worker_id))

        if len(worker_ids) == 0:
            print("%s: no workers reporting (could be due to no jobs)" % worker_type)
            worker_type, None, None

        results = ThreadPool(WORKERTYPE_THREAD_COUNT).starmap(
            self.device_fitness_report, worker_ids
        )
        worker_results = []
        for worker_id, result, _error in results:
            # print("%s: %s" % (worker_id, result))
            result["worker_id"] = worker_id
            worker_results.append(result)
        return worker_type, worker_results, None

    def device_fitness_report(self, queue, worker_group, device):
        results = self.get_worker_jobs(queue, worker_group, device)
        task_successes = 0
        task_failures = 0
        task_runnings = 0
        # pprint.pprint(results)
        # print("queue/device: %s/%s" % (queue, device))
        # print(
        #     "- https://tools.taskcluster.net/provisioners/proj-autophone/worker-types/%s/workers/bitbar/%s"
        #     % (queue, device)
        # )

        task_ids = []
        # import pprint
        # pprint.pprint(results)
        for task in results["recentTasks"]:
            task_id = task["taskId"]
            task_ids.append(task_id)

        results = ThreadPool(TASK_THREAD_COUNT).imap_unordered(
            self.get_task_status, task_ids
        )
        for task_id, result, error in results:
            if error is None:
                task_state = None
                # filter out jobs that are gone
                if "code" in result:
                    if result["code"] == "ResourceNotFound":
                        continue
                try:
                    task_state = result["status"]["state"]
                except KeyError:
                    print("strange result: ")
                    pprint.pprint(result)
                    print(result["code"] == "ResourceNotFound")
                    continue
                if task_state == "running":
                    task_runnings += 1
                elif task_state == "completed":
                    task_successes += 1
                elif task_state == "failed":
                    task_failures += 1
                if self.verbosity:
                    print("%s.%s: %s: %s" % (queue, device, task_id, task_state))
            else:
                # TODO: should return exception? only getting partial truth...
                pass
                # print("error fetching %r: %s" % (task_id, error))

        total = task_failures + task_successes
        if total > 0:
            success_ratio = task_successes / total
            # print("sr: %s/%s=%s" % (task_successes, total, success_ratio))
            results_obj = {
                "success_ratio": round(success_ratio, 2),
                "successes": task_successes,
                "completed": total,
                "running": task_runnings,
            }
            if success_ratio < self.alert_percent:
                results_obj["alert"] = "Low health (less than %s)!" % self.alert_percent
        else:
            results_obj = {"alert": "No work done!"}
        return device, results_obj, None

    def fetch_url(self, url):
        try:
            response = urlopen(url)
            return url, response.read(), None
        except Exception as e:
            return url, None, e

    # handles continuationToken
    def get_jsonc2(self, an_url):
        headers = {"User-Agent": USER_AGENT_STRING}
        retries_left = 2

        while retries_left >= 0:
            if self.verbosity > 2:
                print(an_url)
            response = requests.get(an_url, headers=headers)
            result = response.text
            try:
                output = json.loads(result)
                # will only break on good decode
                break
            except json.decoder.JSONDecodeError as e:
                logger.warning("json decode error. input: %s" % result)
                if retries_left == 0:
                    return an_url, None, e
            retries_left -= 1

        while "continuationToken" in output:
            payload = {"continuationToken": output["continuationToken"]}
            if self.verbosity > 2:
                print("%s, %s" % (an_url, output["continuationToken"]))
            response = requests.get(an_url, headers=headers, params=payload)
            result = response.text
            output = json.loads(result)
        return an_url, output, None

    # handles continuationToken
    def get_jsonc(self, an_url):
        headers = {"User-Agent": USER_AGENT_STRING}
        retries_left = 2

        while retries_left >= 0:
            if self.verbosity > 2:
                print(an_url)
            response = requests.get(an_url, headers=headers)
            result = response.text
            try:
                output = json.loads(result)
                # will only break on good decode
                break
            except json.decoder.JSONDecodeError as e:
                logger.warning("json decode error. input: %s" % result)
                if retries_left == 0:
                    raise e
            retries_left -= 1

        while "continuationToken" in output:
            payload = {"continuationToken": output["continuationToken"]}
            if self.verbosity > 2:
                print("%s, %s" % (an_url, output["continuationToken"]))
            response = requests.get(an_url, headers=headers, params=payload)
            result = response.text
            output = json.loads(result)
        return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        dest="log_level",
        default=0,
        help="specify multiple times for even more verbosity.",
    )
    parser.add_argument(
        "-a",
        "--alert-percent",
        default=ALERT_PERCENT,
        type=float,
        help="percentage of successful jobs to alert at. 0 to 1, defaults to %s."
        % ALERT_PERCENT,
    )
    parser.add_argument(
        "-p",
        "--provisioner",
        default=DEFAULT_PROVISIONER,
        metavar="provisioner",
        help="provisioner to inspect, defaults to %s." % DEFAULT_PROVISIONER,
    )
    parser.add_argument(
        "worker_type_id",
        metavar="worker_type[.worker_id]",
        help="e.g. 'gecko-t-bitbar-gw-perf-p2.pixel2-21' or 'gecko-t-bitbar-gw-batt-g5'",
        nargs="?",
    )

    args = parser.parse_args()

    if not (0 < args.alert_percent < 1):
        print("ERROR: --alert-percent must be between 0 and 1.")
        sys.exit(1)

    worker_type = None
    worker_id = None
    if args.worker_type_id:
        worker_type_id_split = args.worker_type_id.split(".")
        worker_type = worker_type_id_split[0]
        if len(worker_type_id_split) == 2:
            worker_id = worker_type_id_split[1]

    # TODO: just pass args?
    f = Fitness(
        log_level=args.log_level,
        provisioner=args.provisioner,
        alert_percent=args.alert_percent,
    )
    f.main(args.provisioner, worker_type, worker_id)
