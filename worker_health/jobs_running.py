#!/usr/bin/env python3

# checks if jobs are running on the workers specified (and if they're quarantined?)

# takes same args as quarantine-tool

import argparse
import re

from worker_health import status

# import ipdb

# TODO: make more useful (not useful via script, not the data we want) or delete


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("provisioner")
    parser.add_argument("worker_type")
    parser.add_argument("host_csv", type=csv_strs)
    args = parser.parse_args()
    args.hosts = args.host_csv

    si = status.Status(args.provisioner, args.worker_type)

    # print(args)

    si.show_jobs_running_report(args.hosts)
