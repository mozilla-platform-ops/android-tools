#!/usr/bin/env python3

# drains host (quarantines and wait for jobs to finish), runs a command, and then lifts the quarantine

# takes same args as quarantine-tool

import argparse
import re
import sys

from worker_health import quarantine, status


def natural_sort_key(s, _nsre=re.compile("([0-9]+)")):
    return [int(text) if text.isdigit() else text.lower() for text in _nsre.split(s)]


def csv_strs(vstr, sep=","):
    """Convert a string of comma separated values to strings
    @returns iterable of strings
    """
    values = []
    for v0 in vstr.split(sep):
        try:
            v = str(v0)
            values.append(v)
        except ValueError as err:
            raise argparse.ArgumentError(
                "Invalid value %s, values must be a number (%s)" % (vstr, err)
            )
    return values


class SafeRunner:
    def __init__(self, provisioner, worker_type):
        self.provisioner = provisioner
        self.worker_type = worker_type

        self.si = status.Status()
        self.q = quarantine.Quarantine()

    def safe_run(self, hostname, command, verbose=True):
        if verbose:
            print(f"{hostname}: adding to quarantine...")
        self.q.quarantine(self.provisioner, self.worker_type, [hostname])
        # TODO: verify?
        if verbose:
            print(f"{hostname}: quarantined.")

        # TODO: wait until drained (not running jobs)
        # self.si.

        # TODO: run command

        # TODO: lift quarantine

        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("provisioner")
    parser.add_argument("worker_type")
    parser.add_argument("host_csv", type=csv_strs)
    parser.add_argument("command", help="command to run locally")
    args = parser.parse_args()
    args.hosts = args.host_csv

    print(args)
    sys.exit(0)

    sr = SafeRunner(args.provisioner, args.worker_type)

    # get user to ack what we're about to do
    print("about to do the following:")
    print("type 'yes' to continue: ")
    user_input = input()
    if user_input != "yes":
        print("user chose to exit")
        sys.exit(0)

    for host in args.hosts:
        print(f"{host}")
        sr.safe_run(host, args.command)
