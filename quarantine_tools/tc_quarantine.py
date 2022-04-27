#!/usr/bin/env python3

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
                # TODO: how to pad to arbitrary length? dynamic coding?
                if self.padding_length == 3:
                    hosts_to_act_on.append("%s%03d" % (self.worker_name_root, int(h)))
                else:
                    raise "not implemented yet!"
            else:
                hosts_to_act_on.append("%s%s" % (self.worker_name_root, h))
        return hosts_to_act_on

    def quarantine(self, device_numbers, duration="10 years"):
        hosts_to_act_on = self.generate_hosts(device_numbers)
        for a_host in hosts_to_act_on:
            if "-" in duration:
                print("lifting quarantine on %s... " % a_host)
            else:
                print("adding %s to quarantine... " % a_host)
            try:
                self.queue.quarantineWorker(
                    self.provisioner_id,
                    self.worker_type,
                    self.worker_group,
                    a_host,
                    {"quarantineUntil": taskcluster.fromNow(duration)},
                )
            except taskcluster.exceptions.TaskclusterRestFailure as e:
                # usually due to worker not being in pool...
                # TODO: inspect message
                print(e)

    def lift_quarantine(self, device_numbers):
        self.quarantine(device_numbers, duration="-1 year")


BitbarP2UnitQuarantine = TCQuarantine(
    "proj-autophone", "gecko-t-bitbar-gw-unit-p2", "bitbar", "pixel2-"
)

BitbarA51PerfQuarantine = TCQuarantine(
    "proj-autophone", "gecko-t-bitbar-gw-perf-a51", "bitbar", "a51-"
)

Talos1804Quarantine = TCQuarantine(
    "releng-hardware",
    "gecko-t-linux-talos-1804",
    "mdc1",
    "t-linux64-ms-",
    padding=True,
    padding_length=3,
)

if __name__ == "__main__":
    import argparse
    import sys

    # TODO: how to avoid having to create these for every pool we want to manipulate?
    # - provide an URL to queue and extract info and create a class?
    #   - e.g. https://firefox-ci-tc.services.mozilla.com/provisioners/releng-hardware/worker-types/gecko-t-linux-talos-1804
    instance_directory = {
        "talos1804": Talos1804Quarantine,
        "bbp2unit": BitbarP2UnitQuarantine,
        "bba51perf": BitbarA51PerfQuarantine,
    }

    parser = argparse.ArgumentParser()

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-l", "--lift", action="store_true", help="lift the quarantine")
    group.add_argument("-q", "--quarantine", action="store_true")

    parser.add_argument("-p", "--pool", required=True)

    parser.add_argument("csv_of_hosts", help="comma separated list of host ids")

    args = parser.parse_args()

    host_numbers = args.csv_of_hosts.split(",")
    # TODO: dedupe this list

    if args.pool not in instance_directory:
        print("invalid pool specified. valid pools are: ")
        print("  %s" % list(instance_directory.keys()))
        sys.exit(1)

    cls_instance = instance_directory[args.pool]

    if args.quarantine:
        cls_instance.quarantine(host_numbers)
    elif args.lift:
        cls_instance.lift_quarantine(host_numbers)
    else:
        raise Exception("should not be here")
