#!/usr/bin/env python3

import argparse
import json
from multiprocessing.pool import ThreadPool
from time import time as timer
from urllib.request import urlopen

import requests

from worker_health import USER_AGENT_STRING, logger

# import pprint
# import sys

# for each queue
#   for each worker
#     for each job listed in https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types/gecko-t-bitbar-gw-unit-p2/workers/bitbar/pixel2-05
#        check result in https://queue.taskcluster.net/v1/task/N8aF_LpZTWO7B1iGbKy3Yw


class Fitness:
    def __init__(self, log_level=0, testing_mode=False):
        self.verbosity = log_level
        pass

    def get_worker_jobs(self, queue, worker):
        return self.get_jsonc(
            "https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types/%s/workers/bitbar/%s"
            % (queue, worker)
        )

    def get_task_status(self, taskid):
        _url, output, exception = self.get_jsonc2(
            "https://queue.taskcluster.net/v1/task/%s/status" % taskid
        )
        return taskid, output, exception

    def main(self, provisioner, worker_type, worker_id):
        # TODO: decide mode based on what's passed in...
        # nothing: provisioner mode, -p, defaults to proj-autophone
        # worker-type: queue mode, input: queue
        # worker-type and worker-id: worker mode, input: queue.worker_id

        if worker_type and worker_id:
            ## host mode
            start = timer()
            worker, res_obj, e = self.device_fitness_report(worker_type, worker_id)
            print("%s: %s" % (worker, res_obj))
            print("Elapsed Time: %s" % (timer() - start,))
        elif worker_type:
            ### queue mode
            # 'gecko-t-bitbar-gw-perf-p2'
            self.workertype_fitness_report(worker_type)
        else:
            ### provisioner mode
            print("provisioner mode: not implemented yet...")

    def get_worker_types(self, provisioner='proj-autophone'):
        # https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types?limit=100
        # TODO: fetch devices
        return self.get_jsonc("https://queue.taskcluster.net/v1/provisioners/%s/worker-types?limit=100" % provisioner)

    def workertype_fitness_report(self, worker_type):
        url = "https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types/%s/workers?limit=100" % worker_type
        workers_result = self.get_jsonc(url)

        worker_ids = []
        for worker in workers_result['workers']:
            worker_id = worker['workerId']
            worker_ids.append((worker_type, worker_id))

        results = ThreadPool(2).starmap(self.device_fitness_report, worker_ids)
        for worker_id, result, _error in results:
            print("%s: %s" % (worker_id, result))
            # if error is None:
            #     task_state = result["status"]["state"]
            #     # print("%r fetched in %ss" % (url, timer() - start))
            #     if task_state == "completed":
            #         task_successes += 1
            #     elif task_state == "failed":
            #         task_failures += 1
            #     if self.verbosity:
            #         print("%s: %s" % (task_id, task_state))

            # else:
            #     print("error fetching %r: %s" % (task_id, error))


    def device_fitness_report(self, queue, device):
        results = self.get_worker_jobs(queue, device)
        task_successes = 0
        task_failures = 0
        # pprint.pprint(results)
        # print("queue/device: %s/%s" % (queue, device))
        # print(
        #     "- https://tools.taskcluster.net/provisioners/proj-autophone/worker-types/%s/workers/bitbar/%s"
        #     % (queue, device)
        # )

        task_ids = []
        for task in results["recentTasks"]:
            task_id = task["taskId"]
            task_ids.append(task_id)

        results = ThreadPool(20).imap_unordered(self.get_task_status, task_ids)
        for task_id, result, error in results:
            if error is None:
                task_state = result["status"]["state"]
                # print("%r fetched in %ss" % (url, timer() - start))
                if task_state == "completed":
                    task_successes += 1
                elif task_state == "failed":
                    task_failures += 1
                if self.verbosity:
                    pass
                    # print("%s: %s" % (task_id, task_state))
            else:
                pass
                # print("error fetching %r: %s" % (task_id, error))

        total = task_failures + task_successes
        success_ratio = task_successes / total
        # print("sr: %s/%s=%s" % (task_successes, total, success_ratio))
        results_obj = {'success_ratio': round(success_ratio, 2),
                        'total': total,
                        'successes': task_successes}
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
        help="specify multiple times for even more verbosity",
    )
    parser.add_argument(
        "-p",
        "--provisioner",
        default="proj-autophone",
        metavar="P",
        help="provisioner to inspect, defaults to proj-autophone",
    )
    parser.add_argument('worker_type_id', metavar='worker_type[.worker_id]',
                    help='', nargs='?')
    args = parser.parse_args()

    worker_type = None
    worker_id = None
    if args.worker_type_id:
        worker_type_id_split = args.worker_type_id.split('.')
        worker_type = worker_type_id_split[0]
        if len(worker_type_id_split) == 2:
            worker_id = worker_type_id_split[1]

    # TODO: just pass args?
    f = Fitness(log_level=args.log_level)
    f.main(args.provisioner, worker_type, worker_id)
