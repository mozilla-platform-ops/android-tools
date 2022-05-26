#!/usr/bin/env python

import json
import os

import taskcluster

from worker_health import fitness


class Quarantine:

    tc_queue = None
    root_url = "https://firefox-ci-tc.services.mozilla.com"

    def __init__(self):
        with open(os.path.expanduser("~/.tc_token")) as json_file:
            data = json.load(json_file)
        creds = {"clientId": data["clientId"], "accessToken": data["accessToken"]}

        self.tc_queue = taskcluster.Queue(
            {"rootUrl": self.root_url, "credentials": creds}
        )

    def quarantine(self, provisioner_id, worker_type, host_arr, duration="10 years"):
        # try to detect worker group
        wgs = self.get_worker_groups(
            provisioner=provisioner_id, worker_type=worker_type
        )
        if len(wgs) > 1:
            raise Exception(
                "can't guess workerGroup, multiple present. support not implemented yet."
            )
        worker_group = wgs[0]

        for a_host in host_arr:
            if "-" in duration:
                print("lifting quarantine on %s... " % a_host)
            else:
                print("adding %s to quarantine... " % a_host)
            try:
                self.tc_queue.quarantineWorker(
                    provisioner_id,
                    worker_type,
                    worker_group,
                    a_host,
                    {"quarantineUntil": taskcluster.fromNow(duration)},
                )
            except taskcluster.exceptions.TaskclusterRestFailure as e:
                # usually due to worker not being in pool...
                # TODO: inspect message
                print(e)

    def lift_quarantine(self, provisioner, worker_type, device_arr):
        self.quarantine(provisioner, worker_type, device_arr, duration="-1 year")

    def get_worker_groups(self, provisioner, worker_type):
        f = fitness.Fitness(log_level=0, provisioner=provisioner, alert_percent=85)
        output = f.get_workers(worker_type)["workers"]
        worker_groups = {}
        for element in output:
            a_worker_group = element["workerGroup"]
            worker_groups[a_worker_group] = True
        return list(worker_groups.keys())

    def get_workers(self, provisioner, worker_type):
        f = fitness.Fitness(log_level=0, provisioner=provisioner, alert_percent=85)
        # TODO: relocate this function to a base lib
        output = f.get_workers(worker_type)
        return output

    def get_quarantined_workers(self, provisioner, worker_type):
        # import ipdb
        # ipdb.set_trace()

        i = 0
        outcome = self.tc_queue.listWorkers(
            provisioner, worker_type, query={"quarantined": "true"}
        )
        while outcome.get("continuationToken"):
            # print('more...')
            if outcome.get("continuationToken"):
                outcome = self.tc_queue.listWorkers(
                    provisioner,
                    worker_type,
                    query={
                        "quarantined": "true",
                        "continuationToken": outcome.get("continuationToken"),
                    },
                )
            i += 1
            # tasks += len(outcome.get('tasks', []))

        quarantined_workers = []
        for item in outcome["workers"]:
            hostname = item["workerId"]
            # print(hostname)
            # pprint.pprint(item)
            quarantined_workers.append(hostname)
        return quarantined_workers

    def print_quarantined_workers(self, provisioner, worker_type):
        output = self.get_quarantined_workers(provisioner, worker_type)
        count = len(output)
        print("quarantined workers (%s): %s" % (count, output))
