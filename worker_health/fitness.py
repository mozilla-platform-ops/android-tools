#!/usr/bin/env python3

import argparse
import json
#import pprint
#import sys

from multiprocessing.pool import ThreadPool
from time import time as timer
# python2
# from urllib2 import urlopen
# python3
from urllib.request import urlopen


import requests

from worker_health import USER_AGENT_STRING, logger

# for each queue
#   for each worker
#     for each job listed in https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types/gecko-t-bitbar-gw-unit-p2/workers/bitbar/pixel2-05
#        check result in https://queue.taskcluster.net/v1/task/N8aF_LpZTWO7B1iGbKy3Yw

class Fitness:

    def __init__(self, log_level=0, testing_mode=False):
        self.verbosity=log_level
        pass

    def get_worker_jobs(self, queue, worker):
        return self.get_jsonc("https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types/%s/workers/bitbar/%s" % (queue, worker))

    def get_task_status(self, taskid):
        return self.get_jsonc("https://queue.taskcluster.net/v1/task/%s/status" % taskid)

    def main(self):
        start = timer()
        self.device_fitness_report('gecko-t-bitbar-gw-unit-p2', 'pixel2-21')
        print("Elapsed Time: %s" % (timer() - start,))
        # self.device_fitness_report('gecko-t-bitbar-gw-unit-p2', 'pixel2-14')


    def device_fitness_report(self, queue, device):
        results = self.get_worker_jobs(queue, device)
        task_successes = 0
        task_failures = 0
        # pprint.pprint(results)
        print("queue/device: %s/%s" % (queue, device))
        print("- https://tools.taskcluster.net/provisioners/proj-autophone/worker-types/%s/workers/bitbar/%s" % (queue, device))
        for task in results['recentTasks']:
            taskid = task['taskId']
            results2 = self.get_task_status(taskid)
            # print("")
            # pprint.pprint(results2)
            task_state = results2['status']['state']

            if task_state == 'completed':
                task_successes += 1
            elif task_state == 'failed':
                task_failures += 1
            if self.verbosity:
                print("%s: %s" % (taskid, task_state))
        total = task_failures + task_successes
        success_ratio = task_successes / total
        print("sr: %s/%s=%s" % (task_successes, total, success_ratio))

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
    args = parser.parse_args()

    # TODO: just pass args?
    f = Fitness(log_level=args.log_level)
    f.main()
