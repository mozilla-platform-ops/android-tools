#!/usr/bin/env python3

"""
Taskcluster Task Creation CLI
Usage example:
  python create_task_test_2.py --queue proj-autophone/gecko-t-bitbar-gw-test-2 --name "example-task" --description "An example task" --owner "aerickson@mozilla.com" --command "/bin/bash -c 'echo hello'" --token <AUTH_TOKEN>
"""

import argparse
import os
import json
import rstr

import taskcluster


class TCClient:
    def __init__(self):
        self.root_url = "https://firefox-ci-tc.services.mozilla.com"
        with open(os.path.expanduser("~/.tc_token")) as json_file:
            data = json.load(json_file)
        creds = {"clientId": data["clientId"], "accessToken": data["accessToken"]}

        self.queue_object = taskcluster.Queue(
            {"rootUrl": self.root_url, "credentials": creds},
        )


def parse_args():
    parser = argparse.ArgumentParser(description="Create a Taskcluster task via GraphQL API.")
    # parser.add_argument('--queue', required=True, help='Taskcluster queue id (e.g. proj-autophone/gecko-t-bitbar-gw-test-2)')
    return parser.parse_args()


# generate strings that match regex
def gen_task_id():
    regex = r"^[A-Za-z0-9_-]{8}[Q-T][A-Za-z0-9_-][CGKOSWaeimquy26-][A-Za-z0-9_-]{10}[AQgw]$"
    return rstr.xeger(regex)


def main():
    # args = parse_args()
    tcclient = TCClient()
    create_task_args = {
        "taskQueueId": "proj-autophone/gecko-t-bitbar-gw-test-2",
        "schedulerId": "taskcluster-ui",
        "created": "2025-08-22T18:18:05.351Z",
        "deadline": "2025-08-22T21:18:05.351Z",
        "payload": {
            "command": [["/bin/bash", "-c", "for ((i=1;i<=60;i++)); do echo $i; sleep 1; done"]],
            "maxRunTime": 90,
        },
        "metadata": {
            "name": "example-task",
            "description": "An **example** task",
            "owner": "aerickson@mozilla.com",
            "source": "https://firefox-ci-tc.services.mozilla.com/tasks/create",
        },
    }
    # create_task_args = {'payload': }
    tcclient.queue_object.createTask(gen_task_id(), create_task_args)


if __name__ == "__main__":
    main()
