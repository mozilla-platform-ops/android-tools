#!/usr/bin/env python3

# checks if jobs are running on the workers specified (and if they're quarantined?)

# takes same args as quarantine-tool

import argparse
import re

from worker_health import status

# import ipdb


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
    # parser.add_argument(
    #     "action",
    #     choices=["lift", "quarantine", "show", "show-all"],
    #     help="action to do",
    # )
    parser.add_argument("host_csv", type=csv_strs)
    args = parser.parse_args()
    args.hosts = args.host_csv

    si = status.Status()

    print(args)

    print(si.jobs_running(args.provisioner, args.worker_type, args.hosts))
    # for host in args.host_csv:
    #     print(host)

    # import ipdb; ipdb.set_trace()
    # taskcluster

    # if args.action == "quarantine":
    #     if args.action_options is None:
    #         parser.error("you must specify a comma-separated string of hosts")
    #     host_arr = args.action_options.split(",")
    #     q = quarantine.Quarantine()
    #     q.quarantine(
    #         args.provisioner,
    #         args.worker_type,
    #         host_arr,
    #     )
    # elif args.action == "lift":
    #     if args.action_options is None:
    #         parser.error("you must specify a comma-separated string of hosts")
    #     host_arr = args.action_options.split(",")
    #     q = quarantine.Quarantine()
    #     q.lift_quarantine(
    #         args.provisioner,
    #         args.worker_type,
    #         host_arr,
    #     )
    # elif args.action == "show":
    #     q = quarantine.Quarantine()
    #     results = q.get_quarantined_workers(
    #         provisioner=args.provisioner, worker_type=args.worker_type
    #     )
    #     if not results:
    #         print("no results")
    #     else:
    #         print(",".join(results))
    # elif args.action == "show-all":
    #     q = quarantine.Quarantine()
    #     results = q.get_workers(args.provisioner, args.worker_type)
    #     # single-line csv
    #     output = ""

    #     # sort just based on the numerical element of the workerId
    #     # how to avoid needing multiple of these for each type?
    #     sorted_list_of_dicts = sorted(
    #         results["workers"],
    #         key=lambda d: "{0:0>8}".format(d["workerId"].replace("macmini-r8-", "")),
    #     )

    #     for item in sorted_list_of_dicts:
    #         output += "%s," % item["workerId"]
    #     # trim last comma off
    #     print(output[0:-1])

    #     # TODO: add switch that uses this mode
    #     # csv
    #     # print("workerId")
    #     # for item in results["workers"]:
    #     #     # print("%s,%s" % (item["workerGroup"], item["workerId"]))
    #     #     print(item["workerId"])
    # else:
    #     parser.error("please specify an action")
