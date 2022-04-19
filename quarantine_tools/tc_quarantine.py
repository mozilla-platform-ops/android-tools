import json
import os

import taskcluster


class TCQuarantine:
    def __init__(
        self,
        provisioner_id,
        worker_type,
        worker_group,
        worker_name_root,
        padding=False,
        padding_length=0,
    ):
        self.provisioner_id = provisioner_id
        self.worker_type = worker_type
        self.worker_group = worker_group
        # used for generation of the full host name
        self.worker_name_root = worker_name_root

        # host formatting options
        self.padding = padding
        self.padding_length = padding_length

        # load creds and set queue object
        with open(os.path.expanduser("~/.tc_quarantine_token")) as json_file:
            data = json.load(json_file)
        creds = {"clientId": data["clientId"], "accessToken": data["accessToken"]}

        self.queue = taskcluster.Queue(
            {
                "rootUrl": "https://firefox-ci-tc.services.mozilla.com",
                "credentials": creds,
            }
        )

    def generate_hosts(self, device_numbers):
        hosts_to_act_on = []
        for h in device_numbers:
            if self.padding:
                if self.padding_length == 3:
                    hosts_to_act_on.append("%s%03d" % (self.worker_name_root, h))
                else:
                    raise "not implemented yet!"
            else:
                hosts_to_act_on.append("%s%s" % (self.worker_name_root, h))

    def quarantine(self, quarantine_until, device_numbers):
        pass

    def lift_quarantine(self, device_numbers):
        for a_host in device_numbers:
            print("removing %s from quarantine... " % a_host)
            try:
                self.queue.quarantineWorker(
                    "releng-hardware",
                    "gecko-t-linux-talos",
                    "mdc1",
                    a_host,
                    {"quarantineUntil": taskcluster.fromNow("-1 year")},
                )
            except taskcluster.exceptions.TaskclusterRestFailure as e:
                # usually due to worker not being in pool...
                # TODO: inspect message
                print(e)


BitbarP2UnitQuarantine = TCQuarantine(
    "proj-autophone", "gecko-t-bitbar-gw-unit-p2", "bitbar", "pixel2-"
)

Talos1804Quarantine = TCQuarantine(
    "releng-hardware",
    "gecko-t-linux-talos",
    "mdc1",
    "t-linux64-ms-",
    padding=True,
    padding_length=3,
)
