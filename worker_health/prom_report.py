# output prometheus line format
#   - intended to be called by telegraf

from worker_health import bitbar_api, devicepool_config, health


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


def dict_array_to_dict_len(dict_array):
    dict_len = {}
    for key in dict_array:
        dict_len[key] = len(dict_array[key])
    return dict_len


if __name__ == "__main__":
    import pprint

    pr_instance = PromReport()

    print("configured devices")
    configured_devices_by_project = pr_instance.dc_instance.get_configured_devices()
    configured_devices_by_project_count = dict_array_to_dict_len(configured_devices_by_project)
    pprint.pprint(configured_devices_by_project_count)
    print("---")

    print("offline devices")
    offline_devices_by_project = pr_instance.get_offline_devices_by_project()
    offline_deviced_by_project_count = dict_array_to_dict_len(offline_devices_by_project)
    pprint.pprint(offline_devices_by_project)
    pprint.pprint(offline_deviced_by_project_count)
    print("---")

    # TODO: get missing devices
