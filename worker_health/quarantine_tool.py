#!/usr/bin/env python3

import argparse
import re

from worker_health import quarantine


def natural_sort_key(s, _nsre=re.compile("([0-9]+)")):
    return [int(text) if text.isdigit() else text.lower() for text in _nsre.split(s)]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-r", "--reason", help="reason why action was taken, stored by TC"
    )
    parser.add_argument("provisioner")
    parser.add_argument("worker_type")
    parser.add_argument(
        "action",
        choices=["lift", "quarantine", "show", "show-all"],
        help="action to do",
    )
    parser.add_argument("action_options", nargs="?")
    args = parser.parse_args()

    if args.action == "quarantine":
        if args.action_options is None:
            parser.error("you must specify a comma-separated string of hosts")
        host_arr = args.action_options.split(",")
        q = quarantine.Quarantine()
        q.quarantine(args.provisioner, args.worker_type, host_arr, reason=args.reason)
    elif args.action == "lift":
        if args.action_options is None:
            parser.error("you must specify a comma-separated string of hosts")
        host_arr = args.action_options.split(",")
        q = quarantine.Quarantine()
        q.lift_quarantine(
            args.provisioner, args.worker_type, host_arr, reason=args.reason
        )
    elif args.action == "show":
        q = quarantine.Quarantine()
        results = q.get_quarantined_workers(
            provisioner=args.provisioner, worker_type=args.worker_type
        )
        if not results:
            print("no results")
        else:
            # human order
            results.sort(key=lambda d: "{0:0>8}".format(d.replace("macmini-r8-", "")))
            print(",".join(results))
    elif args.action == "show-all":
        q = quarantine.Quarantine()
        results = q.get_workers(args.provisioner, args.worker_type)
        # single-line csv
        output = ""

        # sort just based on the numerical element of the workerId
        # how to avoid needing multiple of these for each type?
        #   - split on '-' and others and use last part?
        sorted_list_of_dicts = sorted(
            results["workers"],
            key=lambda d: "{0:0>8}".format(d["workerId"].replace("macmini-r8-", "")),
        )

        for item in sorted_list_of_dicts:
            output += "%s," % item["workerId"]
        # trim last comma off
        print(output[0:-1])

        # TODO: add switch that uses this mode
        # csv
        # print("workerId")
        # for item in results["workers"]:
        #     # print("%s,%s" % (item["workerGroup"], item["workerId"]))
        #     print(item["workerId"])
    else:
        parser.error("please specify an action")
