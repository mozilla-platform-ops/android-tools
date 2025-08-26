#!/usr/bin/env python3

"""
Taskcluster Task Creation CLI
Usage example:
  python create_task_test_2.py --queue proj-autophone/gecko-t-bitbar-gw-test-2 --name "example-task" --description "An example task" --owner "aerickson@mozilla.com" --command "/bin/bash -c 'echo hello'" --token <AUTH_TOKEN>

Creating a token:
  Create a token at
   https://firefox-ci-tc.services.mozilla.com/auth/clients
  with the following scopes:
    queue:create-task:*
    queue:quarantine-worker:*
    queue:scheduler-id:*
  Place the ~/.tc_token file with contents simlar to:
    {
        "clientId": "mozilla-auth0/ad|Mozilla-LDAP|...",
        "accessToken": "<ACCESS_TOKEN>"
    }
"""

import argparse
import os
import json
import rstr
import time

import alive_progress
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
    default_bash_command = "for ((i=1;i<=60;i++)); do echo $i; sleep 1; done"
    parser = argparse.ArgumentParser(description="Create a Taskcluster task via GraphQL API.")
    parser.add_argument(
        "--queue",
        "-q",
        required=True,
        help="Taskcluster queue id (e.g. proj-autophone/gecko-t-bitbar-gw-test-2)",
    )
    parser.add_argument("--count", "-c", type=int, default=1, help="Number of tasks to create (default: 1)")
    parser.add_argument(
        "--bash-command",
        "-b",
        default=default_bash_command,
        help=f"Command to run in the task (default: {default_bash_command})",
    )
    parser.add_argument(
        "--dry-run",
        "-D",
        action="store_true",
        help="Simulate task creation without actually creating tasks",
    )
    return parser.parse_args()


# generate strings that match regex
def gen_task_id():
    regex = r"^[A-Za-z0-9_-]{8}[Q-T][A-Za-z0-9_-][CGKOSWaeimquy26-][A-Za-z0-9_-]{10}[AQgw]$"
    return rstr.xeger(regex)


def main():
    args = parse_args()
    tcclient = TCClient()

    # prepare args
    user = os.environ.get("USER")

    # use alive-progress
    with alive_progress.alive_bar(args.count, unit=" jobs", enrich_print=False) as bar:
        for i in range(args.count):
            # format: "2025-08-22T18:18:05.351Z"
            datetime_string_format = "%Y-%m-%dT%H:%M:%S.000Z"
            current_time = time.strftime(datetime_string_format, time.gmtime())
            three_hours_from_now = time.strftime(datetime_string_format, time.gmtime(time.time() + 3 * 60 * 60))
            task_id = gen_task_id()

            create_task_args = {
                "taskQueueId": args.queue,
                # "schedulerId": "taskcluster-ui",
                "created": current_time,
                "deadline": three_hours_from_now,
                "payload": {
                    "command": [["/bin/bash", "-c", args.bash_command]],
                    "maxRunTime": 90,
                },
                "metadata": {
                    "name": "test-task",
                    "description": "An **example** test task",
                    "owner": f"{user}@mozilla.com",
                    "source": "http://github.com/mozilla-platform-ops/android-tools",
                },
            }
            if not args.dry_run:
                tcclient.queue_object.createTask(task_id, create_task_args)
                print(f"Task created successfully (https://firefox-ci-tc.services.mozilla.com/tasks/{task_id}).")
            else:
                time.sleep(0.1)
                print(f"[Dry Run] Task ID would be: {task_id}")
            bar()


if __name__ == "__main__":
    main()
