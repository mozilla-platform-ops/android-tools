#!/usr/bin/env python

import taskcluster
import json
import os
import sys

#
# docs: https://pypi.org/project/taskcluster/
#

with open(os.path.expanduser('~/.tc_quarantine_token')) as json_file:
    data = json.load(json_file)
creds = {"clientId": data['clientId'],
         "accessToken": data['accessToken']}

queue = taskcluster.Queue(
    {"rootUrl": "https://firefox-ci-tc.services.mozilla.com", "credentials": creds}
)

queue.quarantineWorker(
    "terraform-packet",
    "gecko-t-linux",
    "packet-sjc1",
    "machine-23",
    {"quarantineUntil": taskcluster.fromNow("-1 year")},
)
