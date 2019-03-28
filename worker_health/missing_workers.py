#!/usr/bin/env python3

import os
import yaml
import json
import subprocess
import pprint


try:
    import urllib.request as urllib_request  # for Python 3
except ImportError:
    import urllib2 as urllib_request  # for Python 2


class WorkerHealth:
    def __init__(self):
        self.devicepool_client_dir = os.path.join(
            "/", "tmp", "worker_health", "mozilla-bitbar-devicepool"
        )
        self.devicepool_git_clone_url = (
            "https://github.com/bclary/mozilla-bitbar-devicepool.git"
        )
        self.pp = pprint.PrettyPrinter(indent=4)
        #
        self.devicepool_config_yaml = None
        self.devicepool_bitbar_device_groups = {}
        # links device groups (in devicepool_bitbar_device_groups) to queues
        self.devicepool_queues_and_workers = {}
        # just the current queue names
        self.tc_current_worker_types = []
        # similar to devicepool_bitbar_device_groups
        self.tc_workers = {}

        # clone or update repo
        self.clone_or_update(self.devicepool_git_clone_url, self.devicepool_client_dir)

    def clone_or_update(self, repo_url, repo_path):
        FNULL = open(os.devnull, "w")
        if os.path.exists(repo_path):
            # update
            os.chdir(repo_path)
            cmd = "git pull --rebase"
            args = cmd.split(" ")
            subprocess.check_call(args, stdout=FNULL, stderr=subprocess.STDOUT)
        else:
            # clone
            cmd = "git clone %s %s" % (repo_url, repo_path)
            args = cmd.split(" ")
            subprocess.check_call(args, stdout=FNULL, stderr=subprocess.STDOUT)

    def get_json(self, an_url):
        req = urllib_request.Request(
            an_url,
            data=None,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:65.0) Gecko/20100101 Firefox/65.0"
            },
        )

        response = urllib_request.urlopen(req)
        result = response.read().decode("utf-8")
        output = json.loads(result)
        return output

    def set_configured_worker_counts(self):
        yaml_file_path = os.path.join(
            self.devicepool_client_dir, "config", "config.yml"
        )
        with open(yaml_file_path, "r") as stream:
            try:
                self.devicepool_config_yaml = yaml.load(stream, Loader=yaml.Loader)
                # self.pp.pprint(self.devicepool_config_yaml)
            except yaml.YAMLError as exc:
                print(exc)

        # get device group data
        for item in self.devicepool_config_yaml["device_groups"]:
            if item.startswith("motog5") or item.startswith("pixel2"):
                # print("*** %s" % item)
                if self.devicepool_config_yaml["device_groups"][item]:
                    keys = self.devicepool_config_yaml["device_groups"][item].keys()
                    # pp.pprint(keys)
                    self.devicepool_bitbar_device_groups[item] = list(keys)
                # print("---")

        # self.pp.pprint(self.devicepool_bitbar_device_groups)

        # link device group data with queue names
        for project in self.devicepool_config_yaml["projects"]:
            if project.endswith("p2") or project.endswith("g5"):
                # print(project)
                # print("  %s" % self.devicepool_config_yaml['projects'][project]['additional_parameters']['TC_WORKER_TYPE'])
                # print("  %s" % self.devicepool_config_yaml['projects'][project]['device_group_name'])
                # if self.devicepool_config_yaml['projects'][project]['device_group_name'] in self.devicepool_bitbar_device_groups[self.devicepool_config_yaml['projects'][project]]:
                try:
                    self.devicepool_queues_and_workers[
                        self.devicepool_config_yaml["projects"][project][
                            "additional_parameters"
                        ]["TC_WORKER_TYPE"]
                    ] = self.devicepool_bitbar_device_groups[
                        self.devicepool_config_yaml["projects"][project][
                            "device_group_name"
                        ]
                    ]
                except KeyError:
                    pass

    def set_current_worker_types(self):
        # get the queues with data
        # https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types?limit=100
        json_1 = self.get_json(
            "https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types?limit=100"
        )
        # self.pp.pprint(json_1)
        for item in json_1["workerTypes"]:
            # self.pp.pprint(item['workerType'])
            self.tc_current_worker_types.append(item["workerType"])

    def set_current_workers(self):
        # get the workers and count of workers
        # https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types/gecko-t-ap-unit-p2/workers?limit=15
        pass

        for item in self.tc_current_worker_types:
            json_result = self.get_json(
                "https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types/%s/workers?limit=50"
                % item
            )
            self.tc_workers[item] = []
            # self.pp.pprint(json_result)
            for worker in json_result["workers"]:
                # print(worker['workerId'])
                self.tc_workers[item].append(worker["workerId"])

    def calculate_utilization_and_dead_hosts(self):
        for item in self.devicepool_queues_and_workers:
            # wh.tc_workers
            print("  %s: " % item)
            print(
                "    https://tools.taskcluster.net/provisioners/proj-autophone/worker-types/%s"
                % item
            )
            # if item in self.tc_workers:
            #     print(self.tc_workers[item])
            # if item in self.devicepool_queues_and_workers:
            #     print(self.devicepool_queues_and_workers[item])
            if item in self.devicepool_queues_and_workers and item in self.tc_workers:
                difference = set(self.devicepool_queues_and_workers[item]) - set(
                    self.tc_workers[item]
                )
                if difference:
                    print("    %s" % difference)
                else:
                    print("    none")


def main():
    wh = WorkerHealth()
    # print("devicepool config data:")
    wh.set_configured_worker_counts()
    # print(wh.devicepool_bitbar_device_groups)
    # print(wh.devicepool_queues_and_workers)
    # print()

    # print("tc current data:")
    wh.set_current_worker_types()
    # print(wh.tc_current_worker_types)
    wh.set_current_workers()
    # print(wh.tc_workers)
    # print()

    print("missing workers (present in config, but not on tc):")
    wh.calculate_utilization_and_dead_hosts()


if __name__ == "__main__":
    main()
