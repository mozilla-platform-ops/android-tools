#!/usr/bin/env python3

import argparse
import json
import os
import pprint
import sys
import taskcluster
from multiprocessing.pool import ThreadPool
from time import time as timer
from urllib.request import urlopen

import requests
from requests.adapters import HTTPAdapter

# from requests.packages.urllib3.util.retry import Retry
from urllib3.util import Retry
from natsort import natsorted
import humanhash

from worker_health import USER_AGENT_STRING, logger
import utils
import quarantine

# for each queue
#   for each worker
#     for each job listed in https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types/gecko-t-bitbar-gw-unit-p2/workers/bitbar/pixel2-05
#        check result in https://queue.taskcluster.net/v1/task/N8aF_LpZTWO7B1iGbKy3Yw

WORKERTYPE_THREAD_COUNT = 4
TASK_THREAD_COUNT = 6
ALERT_PERCENT = 0.85
DEFAULT_PROVISIONER = "proj-autophone"


# https://www.peterbe.com/plog/best-practice-with-retries-with-requests
def requests_retry_session(
    retries=3, backoff_factor=0.3, status_forcelist=(500, 502, 504), session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class Fitness:
    def __init__(
        self,
        log_level=0,
        provisioner=DEFAULT_PROVISIONER,
        alert_percent=ALERT_PERCENT,
        testing_mode=False,
    ):
        self.args = None
        self.verbosity = log_level
        self.humanize_hashes = False
        self.alert_percent = alert_percent
        self.provisioner = provisioner
        self.queue_counts = {}
        self.worker_id_maxlen = 0
        self.quarantine = quarantine.Quarantine()
        self.quarantine_data = {}

    def get_worker_jobs(self, queue, worker_type, worker):
        # TODO: need to get worker-group...
        return utils.get_jsonc(
            "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/provisioners/%s/worker-types/%s/workers/%s/%s"
            # "https://queue.taskcluster.net/v1/provisioners/%s/worker-types/%s/workers/%s/%s"
            % (self.provisioner, queue, worker_type, worker),
            self.verbosity,
        )

    def get_task_status(self, taskid):
        _url, output, exception = self.get_jsonc2(
            "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/%s/status"
            % taskid
            # "https://queue.taskcluster.net/v1/task/%s/status" % taskid
        )
        return taskid, output, exception

    def format_workertype_fitness_report_result(self, res):
        return_string = ""
        worker_id = res["worker_id"]
        del res["worker_id"]

        if self.args.humanize_hashes:
            # TODO: have to do this per worker type? ugh!!!!!
            # - currently only works for aws-metal (probably other tc worker ids also though...)
            #   - format: i-${hexhash}
            h_sanitized = worker_id.split("-")[1]
            hh = humanhash.humanize(h_sanitized, words=3)
            return_string += ("%s (%s)" % (worker_id, hh)).ljust(
                self.worker_id_maxlen + 36
            )
        else:
            return_string += worker_id.ljust(self.worker_id_maxlen + 2)
        return_string += self.sr_dict_format(res)
        return return_string

    def main(self, provisioner, worker_type, worker_id):
        # TODO: show when worker last started a task (taskStarted in TC)
        # - aws metal nodes has quarantined nodes that have been deleted that never drop off from worker-data

        start = timer()
        worker_count = 0
        # TODO: for this calculation, should we use a count of hosts that are reporting (vs all)?
        sr_total = 0
        ## host mode
        if worker_type and worker_id:
            worker_count = 1
            self.get_pending_tasks_multi([worker_type])
            url = (
                "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/provisioners/%s/worker-types/%s/workers?limit=5"
                # "https://queue.taskcluster.net/v1/provisioners/%s/worker-types/%s/workers?limit=5"
                % (self.provisioner, worker_type)
            )
            # print(url)
            worker_group_result = utils.get_jsonc(url, self.verbosity)
            # worker_group = worker_group_result['workerTypes'][0][]
            # import pprint
            # pprint.pprint(worker_group_result)
            # sys.exit()
            if len(worker_group_result["workers"]) == 0:
                print("%s.%s: %s" % (worker_type, worker_id, "no data"))
                return
            worker_group = worker_group_result["workers"][0]["workerGroup"]
            _worker, res_obj, _e = self.device_fitness_report(
                worker_type, worker_group, worker_id
            )
            res_obj["worker_id"] = worker_id
            sr_total += res_obj["sr"]
            print(
                "%s.%s"
                % (worker_type, self.format_workertype_fitness_report_result(res_obj))
            )
        else:
            ### queue mode
            if worker_type:
                worker_types = [worker_type]
            ### provisioner mode
            else:
                worker_types_result = self.get_worker_types(provisioner)
                worker_types = []
                if "workerTypes" in worker_types_result:
                    for provisioner in worker_types_result["workerTypes"]:
                        worker_type = provisioner["workerType"]
                        worker_types.append(worker_type)
                    # print(worker_types)
                else:
                    logger.warning(
                        "error fetching workerTypes, results are incomplete!"
                    )
            self.get_pending_tasks_multi(worker_types)

            # TODO: process and then display? padding of worker_id is not consistent for whole provisioner report
            # - because we haven't scanned the potentially longest worker_ids when we display the first worker_group's data
            for a_worker_type in worker_types:
                wt, res_obj, _e = self.workertype_fitness_report(a_worker_type)
                for item in res_obj:
                    worker_count += 1
                    sr_total += item["sr"]
                    if self.args.only_show_alerting:
                        if "alerts" in item:
                            print(
                                "%s.%s"
                                % (
                                    wt,
                                    self.format_workertype_fitness_report_result(item),
                                )
                            )
                    else:
                        print(
                            "%s.%s"
                            % (wt, self.format_workertype_fitness_report_result(item))
                        )
        # if to protect from divide by 0 (happens on request failures)
        if worker_count:
            # TODO: show alerting count
            print(
                "%s workers queried in %s seconds, average SR %s%%"
                % (
                    worker_count,
                    round((timer() - start), 2),
                    round((sr_total / worker_count * 100), 2),
                )
            )

    def get_pending_tasks(self, queue):
        _url, output, exception = self.get_jsonc2(
            "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/pending/%s/%s"
            # "https://queue.taskcluster.net/v1/pending/%s/%s"
            % (self.provisioner, queue)
        )
        return queue, output, exception

    def get_pending_tasks_multi(self, queues):
        try:
            results = ThreadPool(TASK_THREAD_COUNT).imap_unordered(
                self.get_pending_tasks, queues
            )
        except Exception as e:
            print(e)
        for queue, result, _error in results:
            self.queue_counts[queue] = result["pendingTasks"]

    # for provisioner report...
    def get_worker_types(self, provisioner):
        # https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types?limit=100
        return utils.get_jsonc(
            "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/provisioners/%s/worker-types?limit=100"
            # "https://queue.taskcluster.net/v1/provisioners/%s/worker-types?limit=100"
            % provisioner,
            self.verbosity,
        )

    def simple_worker_report(
        self, worker_type, worker_prefix="packet-", worker_count=60
    ):
        url = (
            "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/provisioners/%s/worker-types/%s/workers?limit=100"
            % (self.provisioner, worker_type)
        )
        # print(url)
        try:
            workers_result = utils.get_jsonc(url, self.verbosity)
        except Exception as e:
            workers_result = []
            print(e)
        # print(workers_result)

        expected_workers = []
        for i in range(0, worker_count):
            expected_workers.append("%s%s" % (worker_prefix, i))

        seen_workers = []
        if "workers" in workers_result:
            for item in workers_result["workers"]:
                seen_workers.append(item["workerId"])
        # pprint.pprint(workers_result)

        # for item in natsorted(seen_workers):
        #     print(item)

        # should show 46
        e_w = set(expected_workers)
        s_w = set(seen_workers)
        # missing = natsorted(s_w.symmetric_difference(e_w))
        missing = e_w - s_w
        m_count = len(missing)
        print("missing workers (%s): %s" % (m_count, sorted(missing)))
        print("%s workers total" % worker_count)

    def get_workers(self, worker_type):
        # TODO: improve this (don't explode if missing)
        with open(os.path.expanduser("~/.tc_token")) as json_file:
            data = json.load(json_file)
        creds = {"clientId": data["clientId"], "accessToken": data["accessToken"]}
        queue = taskcluster.Queue(
            {
                "rootUrl": "https://firefox-ci-tc.services.mozilla.com",
                "credentials": creds,
            }
        )

        outcome = queue.listWorkers(self.provisioner, worker_type)
        return outcome

    def workertype_fitness_report(self, worker_type):
        # load quarantine data
        self.quarantine_data[worker_type] = self.quarantine.get_quarantined_workers(
            self.provisioner, worker_type
        )

        outcome = self.get_workers(worker_type)

        worker_ids = []
        for worker in outcome["workers"]:
            worker_id = worker["workerId"]
            worker_group = worker["workerGroup"]
            self.worker_id_maxlen = max(len(worker_id), self.worker_id_maxlen)
            worker_ids.append((worker_type, worker_group, worker_id))

        if len(worker_ids) == 0:
            print("%s: no workers reporting (could be due to no jobs)" % worker_type)
            worker_type, None, None

        results = []
        try:
            results = ThreadPool(WORKERTYPE_THREAD_COUNT).starmap(
                self.device_fitness_report, worker_ids
            )
        except Exception as e:
            print(e)
        worker_results = []
        for a_tuple in results:
            worker_id = a_tuple[0]
            result = a_tuple[1]
            # error = a_tuple[2]
            if result:
                result["worker_id"] = worker_id
                worker_results.append(result)
        # sort naturally/numerically
        if self.args.sort_order == "sr":
            worker_results = natsorted(worker_results, key=lambda i: i["sr"])
        elif self.args.sort_order == "worker_id":
            worker_results = natsorted(worker_results, key=lambda i: i["worker_id"])
        else:
            raise Exception("unknown sort_order (%s)" % self.args.sort_order)
        return worker_type, worker_results, None

    # basically how print does it but with float padding
    def sr_dict_format(self, sr_dict):
        if not isinstance(sr_dict, dict):
            raise Exception("input should be a dict")
        result_string = "{"
        for key, value in sr_dict.items():
            result_string += "%s: " % key
            if isinstance(value, str):
                result_string += "'%s'" % value
            elif isinstance(value, int):
                result_string += "{:2d}".format(value)
            elif isinstance(value, list):
                result_string += pprint.pformat(value)
            elif isinstance(value, float):
                # the only float is success rate
                result_string += self.graph_percentage(value)
                result_string += " {:.1%}".format(value).rjust(7)
            else:
                raise Exception("unknown type")
            result_string += ", "
        # on last, trim the space
        result_string = result_string[0:-2]
        result_string += "}"
        return result_string

    def device_fitness_report(self, queue, worker_group, device):
        results = self.get_worker_jobs(queue, worker_group, device)
        task_successes = 0
        task_failures = 0
        task_runnings = 0
        task_exceptions = 0
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

        try:
            results = ThreadPool(TASK_THREAD_COUNT).imap_unordered(
                self.get_task_status, task_ids
            )
        except Exception as e:
            print(e)
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
                # TODO: gather exception stats
                if task_state == "running":
                    task_runnings += 1
                elif task_state == "exception":
                    task_exceptions += 1
                elif task_state == "failed":
                    task_failures += 1
                elif task_state == "completed":
                    retries_left = result["status"]["retriesLeft"]
                    if retries_left != 5:
                        runs = result["status"]["runs"]
                        for run in runs:
                            if run["workerId"] == device:
                                run_state = run["state"]
                                if run_state == "exception":
                                    task_exceptions += 1
                                elif run_state == "running":
                                    task_runnings += 1
                                elif run_state == "completed":
                                    task_successes += 1
                                elif run_state == "failed":
                                    task_failures += 1
                                else:
                                    raise Exception("Shouldn't be here!")
                    else:
                        task_successes += 1
                if self.verbosity:
                    print("%s.%s: %s: %s" % (queue, device, task_id, task_state))
            else:
                # TODO: should return exception? only getting partial truth...
                pass
                # print("error fetching %r: %s" % (task_id, error))

        total = task_failures + task_successes
        results_obj = {}
        success_ratio_calculated = False
        if total > 0:
            success_ratio = task_successes / total
            # print("sr: %s/%s=%s" % (task_successes, total, success_ratio))
            results_obj["sr"] = success_ratio
            success_ratio_calculated = True
        else:
            results_obj["sr"] = float(0)
        results_obj["suc"] = task_successes
        results_obj["cmp"] = total
        results_obj["exc"] = task_exceptions
        results_obj["rng"] = task_runnings

        # note if no jobs in queue
        if queue in self.queue_counts:
            if self.queue_counts[queue] == 0:
                # TODO: use setdefault
                if not "notes" in results_obj:
                    results_obj["notes"] = []
                results_obj["notes"].append("No jobs in queue.")
        else:
            logger.warn("Strange, no queue count data for %s" % queue)
        # alert if success ratio is low
        if success_ratio_calculated:
            if success_ratio < self.alert_percent:
                if not "alerts" in results_obj:
                    results_obj["alerts"] = []
                results_obj["alerts"].append(
                    "Low health (less than %s)!" % self.alert_percent
                )
        # alert if no work done
        if total == 0 and task_exceptions == 0 and task_runnings == 0:
            if not "alerts" in results_obj:
                results_obj["alerts"] = []
            results_obj["alerts"].append("No work done!")
        # quarantine
        if device in self.quarantine_data[queue]:
            if not "alerts" in results_obj:
                results_obj["alerts"] = []
            results_obj["alerts"].append("Quarantined.")

        return device, results_obj, None

    def fetch_url(self, url):
        try:
            response = urlopen(url)
            return url, response.read(), None
        except Exception as e:
            return url, None, e

    def graph_percentage(self, value, show_label=False, round_value=False):
        return_string = ""
        if round_value:
            value = round(value, 1)
        if show_label:
            return_string += "%s: "
        return_string += "["
        for i in range(1, 11):
            if value >= i * 0.1:
                return_string += u"="
            else:
                return_string += " "
        return_string += "]"
        return return_string

    # handles continuationToken
    def get_jsonc2(self, an_url):
        headers = {"User-Agent": USER_AGENT_STRING}
        retries_left = 2

        while retries_left >= 0:
            if self.verbosity > 2:
                print(an_url)
            response = requests_retry_session().get(an_url, headers=headers)
            result = response.text
            try:
                output = json.loads(result)
                # will only break on good decode
                break
            except json.decoder.JSONDecodeError as e:
                logger.warning("json decode error. input: %s" % result)
                if retries_left == 0:
                    return an_url, None, e
            print("request failure, manual retry")
            retries_left -= 1

        while "continuationToken" in output:
            payload = {"continuationToken": output["continuationToken"]}
            if self.verbosity > 2:
                print("%s, %s" % (an_url, output["continuationToken"]))
            response = requests_retry_session().get(
                an_url, headers=headers, params=payload
            )
            result = response.text
            output = json.loads(result)
        return an_url, output, None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # TODO: currently only sorts within worker-group (so sometimes results aren't sorted)... ideally sort all results.
    parser.add_argument(
        "-s",
        "--success_rate",
        action="store_const",
        const="sr",
        default="worker_id",  # sorts by worker name by default
        dest="sort_order",
        help="sort results by success rate (default is worker_id).",
    )
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
        "-o",
        "--only-show-alerting",
        action="store_true",
        default=False,
        help="only show alerting hosts",
    )
    parser.add_argument(
        "-p",
        "--provisioner",
        default=DEFAULT_PROVISIONER,
        metavar="provisioner",
        help="provisioner to inspect, defaults to %s." % DEFAULT_PROVISIONER,
    )
    parser.add_argument(
        "-hh",
        "--humanize-hashes",
        default=False,
        action="store_true",
        help="hostnames are human-hashed",
    )
    parser.add_argument(
        "worker_type_id",
        metavar="worker_type[.worker_id]",
        help="e.g. 'gecko-t-bitbar-gw-perf-p2.pixel2-21' or 'gecko-t-bitbar-gw-batt-g5'",
        nargs="?",
    )

    args = parser.parse_args()
    # print(args)
    # sys.exit(0)

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

    f = Fitness(
        log_level=args.log_level,
        provisioner=args.provisioner,
        alert_percent=args.alert_percent,
    )
    # TODO: just pass args?
    f.args = args
    f.main(args.provisioner, worker_type, worker_id)
