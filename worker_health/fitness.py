#!/usr/bin/env python3

import argparse
import json
import pprint
import sys

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
        self.device_fitness_report('gecko-t-bitbar-gw-unit-p2', 'pixel2-21')
        # self.device_fitness_report('gecko-t-bitbar-gw-unit-p2', 'pixel2-14')


    def device_fitness_report(self, queue, device):
        results = self.get_worker_jobs(queue, device)
        task_successes = 0
        task_failures = 0
        # pprint.pprint(results)
        print("queue/device: %s/%s" % (queue, device))
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

            print("%s: %s" % (taskid, task_state))
        success_ratio = task_successes / (task_failures + task_successes)
        print("sr: %s" % success_ratio)


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
        "-t",
        "--time-limit",
        type=int,
        default=95,
        help="for tc, devices are missing if not reporting for longer than this many minutes. defaults to 95.",
    )
    parser.add_argument(
        "--testing-mode",
        action="store_true",
        default=False,
        help="enable testing mode (special schedule).",
    )
    args = parser.parse_args()

    # TODO: just pass args?
    f = Fitness()
    f.main()
