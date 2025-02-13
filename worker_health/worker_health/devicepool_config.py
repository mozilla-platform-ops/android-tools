class DevicepoolConfig:

    def __init__(self):
        self.configured_devices = {}

        # TODO: if repo doesn't exist, clone
        # TODO: if repo exists, pull
        # TODO: parse the config file
        # TODO: define a dict like:
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

    def get_configured_devices(self):
        return self.configured_devices
