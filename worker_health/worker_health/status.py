#!/usr/bin/env python3

import json
import os
import pprint

import fitness
import taskcluster

# listWorkers(provisionerId, workerType, {continuationToken, limit, quarantined, workerState}) : result
# list workers: si.tc_wm.listWorkers('releng-hardware', 'gecko-t-osx-1015-r8')

# pool id is "<provisionerId>/<workerType>" i think
# workergroup is mdc1
# TODO: find api to get workerGroups
# worker(workerPoolId, workerGroup, workerId) : result

#   'workerGroup': 'mdc1',
#   'workerId': 'macmini-r8-83',
#   'workerPoolId': 'releng-hardware/gecko-t-osx-1015-r8'},
# si.tc_wm.worker('releng-hardware/gecko-t-osx-1015-r8', 'mdc1', 'macmini-r8-83')
#
# doesn't work because WM doesn't know about these worker types (standalone provisioner)


class Status:
    tc_wm = None
    root_url = "https://firefox-ci-tc.services.mozilla.com"

    def __init__(self):
        with open(os.path.expanduser("~/.tc_token")) as json_file:
            data = json.load(json_file)
        creds = {"clientId": data["clientId"], "accessToken": data["accessToken"]}

        self.tc_wm = taskcluster.WorkerManager(
            {"rootUrl": self.root_url, "credentials": creds}
        )

    def jobs_running(self, provisioner, worker_type, hosts):
        f = fitness.Fitness(provisioner)
        pprint.pprint(f.get_workers())
        pass

    def list_workers(self, provisioner, worker_type):
        results = self.tc_wm.listWorkers(provisioner, worker_type)
        for result in results["workers"]:
            pprint.pprint(result)


if __name__ == "__main__":
    si = Status()
    si.jobs_running("releng-hardware", "gecko-t-osx-1015-r8", [])
    # import ipdb; ipdb.set_trace()
