#!/usr/bin/env python3

import argparse
import taskcluster
import json
import os
import pprint
import sys


parser = argparse.ArgumentParser(description="show quarntined tc workers")
parser.add_argument("provisioner", help="")
parser.add_argument("worker_type", help="")
args = parser.parse_args()

with open(os.path.expanduser("~/.tc_token")) as json_file:
    data = json.load(json_file)
creds = {"clientId": data["clientId"], "accessToken": data["accessToken"]}

queue = taskcluster.Queue(
    {"rootUrl": "https://firefox-ci-tc.services.mozilla.com", "credentials": creds}
)

# import ipdb
# ipdb.set_trace()

provisioner = args.provisioner
worker_type = args.worker_type

i = 0
tasks = 0
outcome = queue.listWorkers(provisioner, worker_type, query={"quarantined": "true"})
while outcome.get("continuationToken"):
    # print('Response %d gave us %d more tasks' % (i, len(outcome['tasks'])))
    print("more...")
    if outcome.get("continuationToken"):
        outcome = queue.listWorkers(
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

pprint.pprint(quarantined_workers)
sys.exit()
