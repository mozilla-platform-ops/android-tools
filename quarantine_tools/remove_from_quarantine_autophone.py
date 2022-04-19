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

# device numbers to remove
host_numbers_to_unquarantine = [17, 19, 20, 21]

# generate the full hostname
hosts_to_unquarantine = []
for h in host_numbers_to_unquarantine:
    hosts_to_unquarantine.append("pixel2-%s" % h)

for a_host in hosts_to_unquarantine:
    print("removing %s from quarantine... " % a_host)
    try:
        queue.quarantineWorker(
            "proj-autophone",
            "gecko-t-bitbar-gw-unit-p2",
            "bitbar",
            a_host,
            {"quarantineUntil": taskcluster.fromNow("-1 year")},
        )
    except taskcluster.exceptions.TaskclusterRestFailure as e:
        # usually due to worker not being in pool...
        # TODO: inspect message
        print(e)
