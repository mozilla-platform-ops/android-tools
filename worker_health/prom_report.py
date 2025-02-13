# output prometheus line format
#   - intended to be called by telegraf

from worker_health import bitbar_api, devicepool_config


class PromReport:

    def __init__(self) -> None:
        self.ba_instance = bitbar_api.BitbarApi()
        self.dc_instance = devicepool_config.DevicepoolConfig()

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


if __name__ == "__main__":
    pr_instance = PromReport()
    pr_instance.get_offline_devices_per_project()
