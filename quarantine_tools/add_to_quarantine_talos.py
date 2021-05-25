#!/usr/bin/env python3

import json
import os
import pprint
import sys

import taskcluster

#
# docs: https://pypi.org/project/taskcluster/
#

# don't need to create separate credentials
# per tomprince:
#   You can use taskcluster signin to get creds (and can use -s <scope>, possibly multiple times, to restrict scopes).

# print("requires manual configuration currently. edit source and rerun.")
# sys.exit()

with open(os.path.expanduser("~/.tc_quarantine_token")) as json_file:
    data = json.load(json_file)
creds = {"clientId": data["clientId"], "accessToken": data["accessToken"]}

queue = taskcluster.Queue(
    {"rootUrl": "https://firefox-ci-tc.services.mozilla.com", "credentials": creds}
)

hosts_to_quarantine = []

# 4/20
# round  1
# host_numbers_to_quarantine = [15, 1, 53, 29, 14]
# round 2
# host_numbers_to_quarantine = [7, 2, 37, 46, 28, 45, 22, 64]
# round 3
# host_numbers_to_quarantine = [68]
# round 4
# host_numbers_to_quarantine = [49, 23, 13, 6]
# round 5
# host_numbers_to_quarantine = range(92, 106)  # 1 over desired
host_numbers_to_quarantine = range(181, 196)  # 1 over desired


for h in host_numbers_to_quarantine:
    hosts_to_quarantine.append("t-linux64-ms-%03d" % h)  # TODO: Need to zero pad


# display
pprint.pprint(hosts_to_quarantine)
# sys.exit()


for a_host in hosts_to_quarantine:
    print("adding %s to quarantine... " % a_host)
    try:
        queue.quarantineWorker(
            "releng-hardware",
            "gecko-t-linux-talos",
            "mdc1",
            a_host,
            {"quarantineUntil": taskcluster.fromNow("10 year")},
        )
    except taskcluster.exceptions.TaskclusterRestFailure as e:
        print("WARNING: issue with %s: %s" % (a_host, e))

sys.exit()
