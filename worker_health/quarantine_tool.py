#!/usr/bin/env python3

import argparse
import re
import pprint

from worker_health import quarantine


def natural_sort_key(s, _nsre=re.compile("([0-9]+)")):
    return [int(text) if text.isdigit() else text.lower() for text in _nsre.split(s)]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("provisioner")
    parser.add_argument("worker_type")

    sub_parsers = parser.add_subparsers(help="action to take:", dest="action")

    # show
    parser_show = sub_parsers.add_parser("show", help="show quarantined hosts")
    parser_show.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="enable verbose output",
    )
    # show-all
    parser_show_all = sub_parsers.add_parser(
        "show-all",
        help="show all hosts in a pool",
    )
    # quarantine
    parser_quarantine = sub_parsers.add_parser(
        "quarantine",
        help="quarantine a set of hosts",
    )
    parser_quarantine.add_argument(
        "-r",
        "--reason",
        help="why the instance is being quarantined",
    )
    parser_quarantine.add_argument("hosts", nargs="?")
    # lift
    parser_lift = sub_parsers.add_parser(
        "lift",
        help="lift the quarantine on a set of hosts",
    )
    parser_lift.add_argument(
        "-r",
        "--reason",
        help="why the quarantine is being lifted",
    )
    parser_lift.add_argument("hosts", nargs="?")

    args = parser.parse_args()

    # import pprint
    # import sys
    # pprint.pprint(args)
    # sys.exit(1)

    if args.action == "quarantine":
        if args.hosts is None:
            parser.error("you must specify a comma-separated string of hosts")
        host_arr = args.hosts.split(",")
        q = quarantine.Quarantine()
        if args.reason:
            q.quarantine(
                args.provisioner,
                args.worker_type,
                host_arr,
                reason=args.reason,
            )
        else:
            q.quarantine(args.provisioner, args.worker_type, host_arr)
    elif args.action == "lift":
        if args.hosts is None:
            parser.error("you must specify a comma-separated string of hosts")
        host_arr = args.hosts.split(",")
        q = quarantine.Quarantine()
        if args.reason:
            q.lift_quarantine(
                args.provisioner,
                args.worker_type,
                host_arr,
                reason=args.reason,
            )
        else:
            q.lift_quarantine(args.provisioner, args.worker_type, host_arr)
    elif args.action == "show":
        q = quarantine.Quarantine()
        # results = q.get_quarantined_workers(provisioner=args.provisioner, worker_type=args.worker_type)
        results = q.get_quarantined_workers_with_details(
            provisioner=args.provisioner,
            worker_type=args.worker_type,
        )
        if not results:
            print("no results")
        else:
            quarantine_info = results["quarantine_info"]
            quarantined_workers = results["quarantined_workers"]
            formatted_workers = sorted(
                quarantined_workers,
                key=lambda d: "{0:0>8}".format(d.replace("macmini-r8-", "")),
            )
            if args.verbose:
                print(", ".join(formatted_workers))
                pprint.pprint(quarantine_info)
            else:
                print(", ".join(formatted_workers))
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
