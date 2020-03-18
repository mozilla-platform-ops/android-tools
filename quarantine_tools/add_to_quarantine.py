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

hosts_to_quarantine = []
packet_hosts_to_quarantine = [4, 6, 10, 13, 14, 16, 43, 53, 54, 65, 68]

for h in packet_hosts_to_quarantine:
  hosts_to_quarantine.append("machine-%s" % h)

for a_host in hosts_to_quarantine:
  queue.quarantineWorker(
      "terraform-packet",
      "gecko-t-linux",
      "packet-sjc1",
      a_host,
      {"quarantineUntil": taskcluster.fromNow("10 year")},
  )
