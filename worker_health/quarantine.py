#!/usr/bin/env python

import taskcluster
import json
import os
import argparse

import pprint


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

    def main_get_quarantined(self):
        parser = argparse.ArgumentParser()
        # ./quarantine.py terraform-packet gecko-t-linux
        parser.add_argument(
            "provisioner",
            help="e.g. 'TC provisioner, terraform-packet' or 'releng-hardware'",
        )
        parser.add_argument(
            "worker_type",
            help="e.g. 'TC worker_type, gecko-t-bitbar-gw-perf-p2.pixel2-21' or 'gecko-t-bitbar-gw-batt-g5'",
        )
        parser.add_argument(
            "-v",
            "--verbose",
            action="count",
            dest="verbose",
            default=0,
            help="specify multiple times for even more verbosity",
        )
        args = parser.parse_args()
        # pprint.pprint(args)
        provisioner = args.provisioner
        worker_type = args.worker_type

        quarantined_workers = self.get_quarantined_workers(provisioner, worker_type)
        if args.verbose:
            print("%s/%s" % (provisioner, worker_type))
        if args.verbose >= 2:
            print(
                "  %s/provisioners/%s/worker-types/%s"
                % (self.root_url, provisioner, worker_type)
            )
        pprint.pprint(quarantined_workers)

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


if __name__ == "__main__":
    q = Quarantine()
    q.main_get_quarantined()
