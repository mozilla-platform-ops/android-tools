# output prometheus line format
#   - intended to be called by telegraf

import pprint
import sys

from worker_health import bitbar_api, devicepool_config, health, tc_jql, utils


class PromReport:

    def __init__(self) -> None:
        self.ba_instance = bitbar_api.BitbarApi()
        self.dc_instance = devicepool_config.DevicepoolConfig()
        self.h_instance = health.Health()

    def get_offline_devices_per_project(self):
        # parses the response from self.get_device_problems()
        data = self.ba_instance.get_device_problems()

        offline_devices = []
        for device_problem in data:
            problems = device_problem["problems"]
            for problem in problems:
                if problem["type"] == "OFFLINE":
                    offline_devices.append(device_problem["deviceModelName"])

        import pprint
        import sys

        pprint.pprint(offline_devices)
        sys.exit()

        return offline_devices

        # TODO: put in dict fomrat

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

        pass

    def prom_report_get_problem_workers(self, time_limit=45, verbosity=0, exclude_quarantined=False):
        import pprint
        import sys

        # TODO: make this run in init
        self.h_instance.gather_data()
        missing_workers = self.h_instance.calculate_missing_workers_from_tc(
            time_limit,
            exclude_quarantined=exclude_quarantined,
        )
        pprint.pprint(missing_workers)

        offline_workers = self.get_offline_devices_per_project()
        # TODO: verify we can merge these...
        pprint.pprint(offline_workers)

        sys.exit(0)

        merged2 = self.dict_merge_with_dedupe(missing_workers, offline_workers)
        return merged2

    def get_offline_devices_by_project(self):
        offline_devices = []
        offline_devices_by_project = {}

        configured_devices = pr_instance.dc_instance.get_configured_devices()
        device_problems = pr_instance.ba_instance.get_device_problems()

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
        # import pprint

        # missing_workers_by_project = {}
        # tardy_workers_by_project = {}
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

        # OLD
        # for workerType in tc_current_worker_types:
        #     url = f"{tc_url_root}/provisioners/{provisioner}/worker-types/{workerType}/workers?limit=100"
        #     print(url)
        #     sys.exit(0)
        #     json_2 = utils.get_jsonc(url, 0)
        #     # pprint.pprint(json_2)
        #     tc_worker_data[workerType] = json_2

        # NEW
        for workerType in tc_current_worker_types:
            workers_arr = []
            data = tc_jql.get_tc_workers(provisioner, workerType)
            # pprint.pprint(data)
            # print("---")
            # pprint.pprint(data['data']['workers']['edges'])
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
            # sys.exit(0)
            tc_worker_data[workerType] = workers_arr

        # pprint.pprint(tc_worker_data)
        # sys.exit(0)
        return tc_worker_data

    # TODO: rename to get_present_workers_by_worker_group
    # TODO: make this return all workerGroups (don't skip lambda)
    def get_present_workers_by_project(self, tc_worker_data):
        present_workers_by_project = {}
        for workerType in tc_worker_data:
            # workerType is something like gecko-t-bitbar-gw-perf-s24
            # pprint.pprint(workerType)
            for item in tc_worker_data[workerType]:
                # project = workerType
                worker_id = item["workerId"]
                # pprint.pprint(worker)
                if workerType in present_workers_by_project:
                    present_workers_by_project[workerType].append(worker_id)
                else:
                    present_workers_by_project[workerType] = [worker_id]
        # pprint.pprint(present_workers_by_project)
        # sys.exit(0)
        return present_workers_by_project

    def get_missing_workers_by_project(self, tc_worker_data):
        configured_devices_by_project = pr_instance.dc_instance.get_configured_devices()
        present_workers_by_project = self.get_present_workers_by_project(tc_worker_data)

        import pprint
        import sys

        # pprint.pprint(configured_devices_by_project)
        # print("---")
        # pprint.pprint(present_workers_by_project)
        # sys.exit(0)

        missing_workers_by_project = {}
        for project in configured_devices_by_project:
            # print(project)
            # if project in configured_devices_by_project:
            #     pprint.pprint(configured_devices_by_project[project])
            # else:
            #     print("project not in present_workers_by_project")
            # if project in present_workers_by_project:
            #     pprint.pprint(present_workers_by_project[project])
            # else:
            #     print("project not in configured_devices_by_project")
            # print("---")
            if project not in present_workers_by_project:
                missing_workers_by_project[project] = configured_devices_by_project[project]
                continue
            missing_workers = list(
                set(configured_devices_by_project[project]) - set(present_workers_by_project[project]),
            )
            # pprint.pprint(missing_workers)
            if missing_workers:
                missing_workers_by_project[project] = missing_workers

        pprint.pprint(missing_workers_by_project)
        sys.exit(0)
        return missing_workers_by_project


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


if __name__ == "__main__":
    pr_instance = PromReport()

    # print("configured devices")
    # configured_devices_by_project = pr_instance.dc_instance.get_configured_devices()
    # configured_devices_by_project_count = dict_array_to_dict_len(configured_devices_by_project)
    # pprint.pprint(configured_devices_by_project)
    # pprint.pprint(configured_devices_by_project_count)
    # print("---")

    # print("offline devices")
    # offline_devices_by_project = pr_instance.get_offline_devices_by_project()
    # offline_deviced_by_project_count = dict_array_to_dict_len(offline_devices_by_project)
    # pprint.pprint(offline_devices_by_project)
    # pprint.pprint(offline_deviced_by_project_count)
    # print("---")

    print("missing/tardy devices")
    tc_worker_data = pr_instance.get_tc_worker_data()
    # calculate missing
    missing_workers_by_project = pr_instance.get_missing_workers_by_project(tc_worker_data)
    pprint.pprint(missing_workers_by_project)
    sys.exit(0)

    # calculate tardy
    tardy_workers_by_project = pr_instance.get_tardy_workers_by_project()
    # merge missing and tardy
    merged = pr_instance.dict_merge_with_dedupe(missing_workers_by_project, tardy_workers_by_project)
    merged_count = dict_array_to_dict_len(merged)
    pprint.pprint(merged)
    pprint.pprint(merged_count)
    print("---")

    # TODO: get missing devices
