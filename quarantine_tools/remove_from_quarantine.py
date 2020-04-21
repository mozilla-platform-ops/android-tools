#!/usr/bin/env python

import taskcluster
import json
import os
import sys

#
# docs: https://pypi.org/project/taskcluster/
#

# don't need to create separate credentials
# per tomprince: 
#   You can use taskcluster signin to get creds (and can use -s <scope>, possibly multiple times, to restrict scopes).

print("requires manual configuration currently. edit source and rerun.")
sys.exit()

with open(os.path.expanduser('~/.tc_quarantine_token')) as json_file:
    data = json.load(json_file)
creds = {"clientId": data['clientId'],
         "accessToken": data['accessToken']}

queue = taskcluster.Queue(
    {"rootUrl": "https://firefox-ci-tc.services.mozilla.com", "credentials": creds}
)

packet_hosts_to_unquarantine = [49, 23, 13, 6]

for h in packet_hosts_to_unquarantine:
  hosts_to_unquarantine.append("machine-%s" % h)

for a_host in hosts_to_unquarantine:
    queue.quarantineWorker(
        "terraform-packet",
        "gecko-t-linux",
        "packet-sjc1",
        a_host
        {"quarantineUntil": taskcluster.fromNow("-1 year")},
    )