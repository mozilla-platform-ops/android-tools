#!/usr/bin/env python3

import taskcluster
import json
import os
import sys


with open(os.path.expanduser('~/.tc_token')) as json_file:
    data = json.load(json_file)
creds = {"clientId": data['clientId'],
         "accessToken": data['accessToken']}

queue = taskcluster.Queue(
    {"rootUrl": "https://firefox-ci-tc.services.mozilla.com", "credentials": creds}
)

# import ipdb
# ipdb.set_trace()

i = 0
tasks = 0
outcome = queue.listWorkers('terraform-packet', 'gecko-t-linux', query={'quarantined': 'true'})
while outcome.get('continuationToken'):
    # print('Response %d gave us %d more tasks' % (i, len(outcome['tasks'])))
    print('more...')
    if outcome.get('continuationToken'):
        outcome = queue.listWorkers('terraform-packet', 'gecko-t-linux', query={'quarantined': 'true', 'continuationToken': outcome.get('continuationToken')})
    i += 1
    # tasks += len(outcome.get('tasks', []))

import pprint

quarantined_workers = []
for item in outcome['workers']:
  hostname = item['workerId']
  # print(hostname)
  # pprint.pprint(item)
  quarantined_workers.append(hostname)

pprint.pprint(quarantined_workers)
sys.exit()
