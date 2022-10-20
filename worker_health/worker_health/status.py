#!/usr/bin/env python3

import json
import os
import pprint

import taskcluster

from worker_health import tc_helpers

# class goal: see if a worker is working


class Status:
    tc_wm = None
    root_url = "https://firefox-ci-tc.services.mozilla.com"

    def __init__(self):
        with open(os.path.expanduser("~/.tc_token")) as json_file:
            data = json.load(json_file)
        creds = {"clientId": data["clientId"], "accessToken": data["accessToken"]}

        self.tc_wm = taskcluster.WorkerManager(
            {"rootUrl": self.root_url, "credentials": creds}
        )

    def show_jobs_running_report(self, provisioner, worker_type, hosts):
        tch = tc_helpers.TCHelper(provisioner=provisioner)
        # issue: doesn't show state (running or idle)
        # pprint.pprint(f.get_workers(worker_type))

        if len(hosts) == 0:
            raise Exception("no hosts specified")

        worker_groups = tch.get_worker_groups(worker_type)
        if len(worker_groups) > 1:
            raise Exception(
                "currently doesn't support worker types with more than one worker group!"
            )
        worker_group = worker_groups[0]

        hosts_with_non_completed_or_failed_jobs = []
        hosts_checked = []
        for host in hosts:
            hosts_checked.append(host)
            results = tch.get_worker_jobs(worker_type, worker_group, host)
            # pprint.pprint(results)
            for result in results["recentTasks"]:
                task_id = result["taskId"]
                # pprint.pprint(task_id)
                _tid, status_blob, _exc = tch.get_task_status(task_id)
                # pprint.pprint(status_blob)
                t_status = status_blob["status"]["state"]
                if t_status != "completed" and t_status != "failed":
                    # pprint.pprint(status_blob["status"]["state"])
                    hosts_with_non_completed_or_failed_jobs.append(host)

        print(f"hosts checked ({len(hosts_checked)}): {hosts_checked}")
        print(
            f"hosts_with_non_completed_or_failed_jobs ({len(hosts_with_non_completed_or_failed_jobs)}): {hosts_with_non_completed_or_failed_jobs}"
        )

        # return hosts not idle
        return hosts_with_non_completed_or_failed_jobs

    def list_workers(self, provisioner, worker_type):
        results = self.tc_wm.listWorkers(worker_type, provisioner)
        pprint.pprint(results)
        for result in results["workers"]:
            pprint.pprint(result)


if __name__ == "__main__":
    si = Status()
    # example usage
    si.show_jobs_running_report(
        "releng-hardware",
        "gecko-t-osx-1015-r8",
        [
            "macmini-r8-1",
            # "macmini-r8-2",
            # "macmini-r8-3",
            # "macmini-r8-4",
            # "macmini-r8-5",
            # "macmini-r8-7",
            # "macmini-r8-8",
            # "macmini-r8-9",
            # "macmini-r8-10",
        ],
    )
    # for futher debugging
    # import ipdb; ipdb.set_trace()
