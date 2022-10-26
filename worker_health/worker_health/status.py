#!/usr/bin/env python3

import json
import os
import pprint
import time

import taskcluster

from worker_health import tc_helpers

# class goal: see if a worker is working


class Status:
    tc_wm = None
    root_url = "https://firefox-ci-tc.services.mozilla.com"

    def __init__(self, provisioner, worker_type):
        self.provisioner = provisioner
        self.worker_type = worker_type

        with open(os.path.expanduser("~/.tc_token")) as json_file:
            data = json.load(json_file)
        creds = {"clientId": data["clientId"], "accessToken": data["accessToken"]}

        self.tc_wm = taskcluster.WorkerManager(
            {"rootUrl": self.root_url, "credentials": creds}
        )
        self.tc_h = tc_helpers.TCHelper(provisioner=self.provisioner)

    def wait_until_no_jobs_running(self, hosts, sleep_seconds=5, show_indicator=True):
        while True:
            jrd = self.get_jobs_running_data(hosts)
            if len(jrd) == 0:
                if show_indicator:
                    print("")
                break
            time.sleep(sleep_seconds)
            if show_indicator:
                print(".", end="")

    def get_jobs_running_data(self, hosts):
        worker_groups = self.tc_h.get_worker_groups(self.worker_type)
        worker_group = worker_groups[0]

        hosts_with_non_completed_or_failed_jobs = []
        hosts_checked = []
        for host in hosts:
            hosts_checked.append(host)
            results = self.tc_h.get_worker_jobs(self.worker_type, worker_group, host)
            # pprint.pprint(results)
            for result in results["recentTasks"]:
                task_id = result["taskId"]
                # pprint.pprint(task_id)
                _tid, status_blob, _exc = self.tc_h.get_task_status(task_id)
                # pprint.pprint(status_blob)
                t_status = status_blob["status"]["state"]
                if (
                    t_status != "completed"
                    and t_status != "failed"
                    and t_status != "exception"
                ):
                    # TODO: show task id and state if in verbose?
                    # pprint.pprint(status_blob["status"]["state"])
                    hosts_with_non_completed_or_failed_jobs.append(host)
        return hosts_with_non_completed_or_failed_jobs

    def show_jobs_running_report(self, hosts):
        hosts_with_non_completed_or_failed_jobs = self.get_jobs_running_data(hosts)
        # less useful now that it's just a len call vs the internal value from above?
        hosts_checked = hosts

        print(f"hosts checked ({len(hosts_checked)}): {hosts_checked}")
        print(
            f"hosts_with_non_completed_or_failed_jobs ({len(hosts_with_non_completed_or_failed_jobs)}): {hosts_with_non_completed_or_failed_jobs}"
        )

        # return hosts not idle
        return hosts_with_non_completed_or_failed_jobs

    # TODO: not used... ok to remove?
    def list_workers(self):
        results = self.tc_wm.listWorkers(self.worker_type, self.provisioner)
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
