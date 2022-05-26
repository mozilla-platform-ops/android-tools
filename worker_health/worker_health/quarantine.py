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

    def set_quarantined_worker(self, provisioner, worker_type, host):
        pass

    def get_workers(self, provisioner, worker_type):
        f = fitness.Fitness(log_level=0, provisioner=provisioner, alert_percent=85)
        # TODO: relocate this function to a base lib
        output = f.get_workers(worker_type)

        the_workers = []
        for item in output["workers"]:
            hostname = item["workerId"]
            # print(hostname)
            # pprint.pprint(item)
            the_workers.append(hostname)
        return the_workers

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
