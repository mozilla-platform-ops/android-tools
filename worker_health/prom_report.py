#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# output prometheus line format
#   - intended to be called by telegraf

import pprint

import pendulum

from worker_health import bitbar_api, devicepool_config, health, tc_jql, utils


class PromReport:

    TIME_LIMIT = 75

    def __init__(self) -> None:
        self.ba_instance = bitbar_api.BitbarApi()
        self.dc_instance = devicepool_config.DevicepoolConfig()
        self.h_instance = health.Health()

    # returns a dict like:
    # {
    #   gecko-t-bitbar-gw-unit-p5: 2,
    #   gecko-t-bitbar-gw-test-1: 0,
    #   gecko-t-bitbar-gw-perf-s24: 1,
    #   gecko-t-bitbar-gw-perf-s21: 2,
    #   gecko-t-bitbar-gw-perf-p6: 0,
    #   gecko-t-bitbar-gw-perf-p5: 0,
    #   gecko-t-bitbar-gw-perf-a55: 2,
    #   gecko-t-bitbar-gw-perf-a51: 9,
    # }
    def get_offline_devices_per_project(self):
        # parses the response from self.get_device_problems()
        data = self.ba_instance.get_device_problems()

        offline_devices = []
        for device_problem in data:
            problems = device_problem["problems"]
            for problem in problems:
                if problem["type"] == "OFFLINE":
                    offline_devices.append(device_problem["deviceModelName"])

        return offline_devices

    def get_offline_devices_by_project(self):
        offline_devices = []
        offline_devices_by_project = {}

        configured_devices = self.dc_instance.get_configured_devices()
        device_problems = self.ba_instance.get_device_problems()

        for item in device_problems:
            for problem in item["problems"]:
                if problem["type"] == "OFFLINE":
                    device_name = item["deviceName"]
                    offline_devices.append(device_name)

        for device in offline_devices:
            for project in configured_devices:
                if device in configured_devices[project]:
                    # add the device name to an array of offline devices for that project
                    if project in offline_devices_by_project:
                        offline_devices_by_project[project].append(device)
                    else:
                        offline_devices_by_project[project] = [device]

        return offline_devices_by_project

    def get_tc_worker_data(self, provisioner="proj-autophone"):
        tc_url_root = "https://firefox-ci-tc.services.mozilla.com/api/queue/v1"
        MAX_WORKER_TYPES = 50

        tc_worker_data = {}

        url = (
            f"{tc_url_root}/provisioners/{provisioner}/worker-types/?limit={MAX_WORKER_TYPES}"
            # "https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types?limit=%s"
        )

        # get the workerTypes in the provisioner
        json_1 = utils.get_jsonc(url, 0)
        tc_current_worker_types = []
        for item in json_1["workerTypes"]:
            tc_current_worker_types.append(item["workerType"])

        # get the data for each workerType
        for workerType in tc_current_worker_types:
            workers_arr = []
            data = tc_jql.get_tc_workers(provisioner, workerType)
            workers_edges = data["data"]["workers"]["edges"]
            for item in workers_edges:
                worker_blob = {}
                worker_id = item["node"]["workerId"]
                # worker_group = item['node']['workerGroup']
                lastDateActive = item["node"]["lastDateActive"]
                worker_blob["workerId"] = worker_id
                # worker_blob['workerGroup'] = worker_group
                worker_blob["lastDateActive"] = lastDateActive
                workers_arr.append(worker_blob)
            tc_worker_data[workerType] = workers_arr

        return tc_worker_data

    # TODO: rename to get_present_workers_by_worker_group
    def get_present_workers_by_project(self, tc_worker_data):
        present_workers_by_project = {}
        for workerType in tc_worker_data:
            # workerType is something like gecko-t-bitbar-gw-perf-s24
            for item in tc_worker_data[workerType]:
                worker_id = item["workerId"]
                if workerType in present_workers_by_project:
                    present_workers_by_project[workerType].append(worker_id)
                else:
                    present_workers_by_project[workerType] = [worker_id]
        return present_workers_by_project

    def get_missing_workers_by_project(self, tc_worker_data):
        configured_devices_by_project = self.dc_instance.get_configured_devices()
        present_workers_by_project = self.get_present_workers_by_project(tc_worker_data)

        missing_workers_by_project = {}
        for project in configured_devices_by_project:
            if project not in present_workers_by_project:
                missing_workers_by_project[project] = configured_devices_by_project[project]
                continue
            missing_workers = list(
                set(configured_devices_by_project[project]) - set(present_workers_by_project[project]),
            )
            if missing_workers:
                missing_workers_by_project[project] = missing_workers

        return missing_workers_by_project

    def get_tardy_workers_by_project(self, tc_worker_data, time_limit=TIME_LIMIT):
        dt = pendulum.now(tz="UTC")
        comparison_dt = dt.subtract(minutes=time_limit)

        tardy_workers_by_project = {}
        for workerType in tc_worker_data:
            for item in tc_worker_data[workerType]:
                worker_id = item["workerId"]
                lastDateActive = pendulum.parse(item["lastDateActive"])
                if lastDateActive < comparison_dt:
                    if workerType in tardy_workers_by_project:
                        tardy_workers_by_project[workerType].append(worker_id)
                    else:
                        tardy_workers_by_project[workerType] = [worker_id]
        return tardy_workers_by_project


def dict_array_to_dict_len(dict_array):
    dict_len = {}
    for key in dict_array:
        dict_len[key] = len(dict_array[key])
    return dict_len


def dict_merge_with_dedupe(dict1, dict2):
    merged = dict1.copy()
    for key in dict2:
        if key in merged:
            merged[key] = list(set(merged[key] + dict2[key]))
        else:
            merged[key] = dict2[key]
    return merged


def test_main():
    pr_instance = PromReport()

    # print("configured devices")
    # configured_devices_by_project = pr_instance.dc_instance.get_configured_devices()
    # configured_devices_by_project_count = dict_array_to_dict_len(configured_devices_by_project)
    # pprint.pprint(configured_devices_by_project)
    # pprint.pprint(configured_devices_by_project_count)
    # print("---")

    # print("offline devices")
    offline_devices_by_project = pr_instance.get_offline_devices_by_project()
    # offline_deviced_by_project_count = dict_array_to_dict_len(offline_devices_by_project)
    # pprint.pprint(offline_devices_by_project)
    # pprint.pprint(offline_deviced_by_project_count)
    # print("---")

    print("missing+offline devices")
    tc_worker_data = pr_instance.get_tc_worker_data()
    # calculate missing
    missing_workers_by_project = pr_instance.get_missing_workers_by_project(tc_worker_data)
    # pprint.pprint(missing_workers_by_project)
    # sys.exit(0)

    # TODO: use tardy?
    # TODO: replace code in fitness with code here
    # calculate tardy
    # tardy_workers_by_project = pr_instance.get_tardy_workers_by_project(tc_worker_data)
    # pprint.pprint(tardy_workers_by_project)
    # sys.exit(0)

    # merge missing and offline
    merged = dict_merge_with_dedupe(missing_workers_by_project, offline_devices_by_project)
    merged_count = dict_array_to_dict_len(merged)
    pprint.pprint(merged)
    pprint.pprint(merged_count)
    print("---")


def prom_report():
    pr_instance = PromReport()

    configured_devices_by_project = pr_instance.dc_instance.get_configured_devices()
    configured_devices_by_project_count = dict_array_to_dict_len(configured_devices_by_project)
    # generate prometheus lines
    for project in configured_devices_by_project:
        print(
            f'worker_health_configured_devices{{workerType="{project}"}} '
            f"{configured_devices_by_project_count[project]}",
        )

    tc_worker_data = pr_instance.get_tc_worker_data()
    offline_devices_by_project = pr_instance.get_offline_devices_by_project()
    missing_workers_by_project = pr_instance.get_missing_workers_by_project(tc_worker_data)
    merged = dict_merge_with_dedupe(missing_workers_by_project, offline_devices_by_project)
    merged_count = dict_array_to_dict_len(merged)
    # generate prometheus lines
    for project in merged:
        print(
            f'worker_health_missing_or_offline_devices{{workerType="{project}"}} '
            f"{
              merged_count[project]
            }",
        )

    pass


if __name__ == "__main__":
    # test_main()
    prom_report()
