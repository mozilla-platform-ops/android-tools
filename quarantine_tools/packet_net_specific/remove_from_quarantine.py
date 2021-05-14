#!/usr/bin/env python3

import json
import os

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

hosts_to_unquarantine = []

# 4/20 incident round 1
# host_numbers_to_unquarantine = [1, 14, 15, 2, 22, 28, 29, 33]
# round 2
# host_numbers_to_unquarantine = [13, 23, 44, 6]
# round 3: can't view logs... unknown
# host_numbers_to_unquarantine = [64, 53]
# round 4
# 49, 68 insufficient bogomips
# 7 fetch issues
# 45, 46 can't view logs (expired)
# 37 unknown
# host_numbers_to_unquarantine = [49, 68, 7, 45, 37, 46]

packet_hosts_to_unquarantine = [68]


for h in packet_hosts_to_unquarantine:
    hosts_to_unquarantine.append("packet-%s" % h)

for a_host in hosts_to_unquarantine:
    print("removing %s from quarantine... " % a_host)
    queue.quarantineWorker(
        "terraform-packet",
        "gecko-t-linux",
        "packet-sjc1",
        a_host,
        {"quarantineUntil": taskcluster.fromNow("-1 year")},
    )
