#!/usr/bin/env python3

"""
create_tc_task.py

Creating a TC token:
  1. Go to URL and create a token:
    https://firefox-ci-tc.services.mozilla.com/auth/clients

    with the following scopes:
      queue:create-task:*
      queue:quarantine-worker:*
      queue:scheduler-id:*
      queue:pending-count:*
      queue:claimed-count:*

  2. Place the ~/.tc_token file with contents similar to:
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

DEFAULT_BASH_COMMAND = "for ((i=1;i<=60;i++)); do echo $i; sleep 1; done"


class TCClient:
    def __init__(self, queue, dry_run=False, bash_command=DEFAULT_BASH_COMMAND, command_timeout_seconds=90):
        self.root_url = "https://firefox-ci-tc.services.mozilla.com"
        try:
            with open(os.path.expanduser("~/.tc_token")) as json_file:
                data = json.load(json_file)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Error reading ~/.tc_token: {e}")
        try:
            creds = {"clientId": data["clientId"], "accessToken": data["accessToken"]}
        except KeyError as e:
            raise RuntimeError(f"Missing key in ~/.tc_token: {e}")
        self.queue = queue
        self.dry_run = dry_run
        self.bash_command = bash_command
        self.command_timeout_seconds = command_timeout_seconds
        self.queue_object = taskcluster.Queue(
            {"rootUrl": self.root_url, "credentials": creds},
        )

    def create_task(self):
        # prepare args
        user = os.environ.get("USER")
        # format: "2025-08-22T18:18:05.351Z"
        datetime_string_format = "%Y-%m-%dT%H:%M:%S.000Z"
        current_time = time.strftime(datetime_string_format, time.gmtime())
        three_hours_from_now = time.strftime(datetime_string_format, time.gmtime(time.time() + 3 * 60 * 60))
        task_id = gen_task_id()

        create_task_args = {
            "taskQueueId": self.queue,
            # "schedulerId": "taskcluster-ui",
            "created": current_time,
            "deadline": three_hours_from_now,
            "payload": {
                "command": [["/bin/bash", "-c", self.bash_command]],
                "maxRunTime": self.command_timeout_seconds,
            },
            "metadata": {
                "name": "test-task",
                "description": "An **example** test task",
                "owner": f"{user}@mozilla.com",
                "source": "http://github.com/mozilla-platform-ops/android-tools",
            },
        }
        if not self.dry_run:
            try:
                self.queue_object.createTask(task_id, create_task_args)
                print(f"Task created successfully (https://firefox-ci-tc.services.mozilla.com/tasks/{task_id}).")
            except Exception as e:
                print(f"Failed to create task: {e}")
        else:
            time.sleep(0.1)
            print(f"[Dry Run] Task ID would be: {task_id}")


def parse_args():
    parser = argparse.ArgumentParser(description="Create a Taskcluster task using the Taskcluster Python client library.")
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
        default=DEFAULT_BASH_COMMAND,
        help=f"Command to run in the task (default: {DEFAULT_BASH_COMMAND})",
    )
    parser.add_argument(
        "--command-timeout",
        "-t",
        type=int,
        default=90,
        help="Command timeout in seconds (default: 90)",
    )
    parser.add_argument(
        "--dry-run",
        "-D",
        action="store_true",
        help="Simulate task creation without actually creating tasks",
    )
    parser.add_argument(
        "--continuous-mode",
        "-C",
        action="store_true",
        help="Enable continuous mode (ensures a continuous load in a queue by monitoring and launching more jobs when the queue is below the limit).",
    )
    parser.add_argument(
        "--continuous-mode-limit",
        "-L",
        type=int,
        default=30,
        help="The minimum number of jobs to keep in the queue (default: 30)",
    )
    parser.add_argument(
        "--continuous-mode-check-interval",
        "-I",
        type=int,
        default=15,
        help="Continuous mode check interval in seconds (default: 15)",
    )
    return parser.parse_args()


# generate strings that match regex
def gen_task_id():
    regex = r"^[A-Za-z0-9_-]{8}[Q-T][A-Za-z0-9_-][CGKOSWaeimquy26-][A-Za-z0-9_-]{10}[AQgw]$"
    return rstr.xeger(regex)


def main():
    args = parse_args()
    tcclient = TCClient(
        args.queue,
        dry_run=args.dry_run,
        bash_command=args.bash_command,
        command_timeout_seconds=args.command_timeout,
    )
    if args.dry_run:
        print("Dry Run mode is enabled. No tasks will be created.")

    if args.continuous_mode:
        print(
            f"Starting in continuous mode with job count {args.count} and limit {args.continuous_mode_limit}. "
            f"Sleeping for {args.continuous_mode_check_interval} seconds between queue checks.",
        )

        # continuous mode
        while True:
            # ctrl-c to exit
            try:
                try:
                    queue_count = tcclient.queue_object.taskQueueCounts(args.queue).get("pendingTasks", 0)
                    print(f"{args.queue} pending tasks: {queue_count}")
                    if queue_count < args.continuous_mode_limit:
                        print(f"Below limit {args.continuous_mode_limit}, starting {args.count} tasks...")
                        for i in range(args.count):
                            tcclient.create_task()
                except Exception as e:
                    if TaskclusterRestFailure and isinstance(e, TaskclusterRestFailure):
                        print(f"Taskcluster API error: {e}")
                    else:
                        print(f"Error fetching queue counts: {e}")
                    print(f"Will retry after {args.continuous_mode_check_interval} seconds.")
                time.sleep(args.continuous_mode_check_interval)
            except KeyboardInterrupt:
                break
    else:
        # one-off mode
        with alive_progress.alive_bar(args.count, unit=" jobs", enrich_print=False) as bar:
            for i in range(args.count):
                tcclient.create_task()
                bar()


if __name__ == "__main__":
    main()
