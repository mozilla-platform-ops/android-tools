#!/usr/bin/env python3

import argparse

from worker_health import quarantine

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
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
        q.quarantine(
            args.provisioner,
            args.worker_type,
            host_arr,
        )
    elif args.action == "lift":
        if args.action_options is None:
            parser.error("you must specify a comma-separated string of hosts")
        host_arr = args.action_options.split(",")
        q = quarantine.Quarantine()
        q.lift_quarantine(
            args.provisioner,
            args.worker_type,
            host_arr,
        )
    elif args.action == "show":
        q = quarantine.Quarantine()
        results = q.get_quarantined_workers(
            provisioner=args.provisioner, worker_type=args.worker_type
        )
        if not results:
            print("no results")
        else:
            print(",".join(results))
    elif args.action == "show-all":
        q = quarantine.Quarantine()
        results = q.get_workers(args.provisioner, args.worker_type)
        # single-line csv
        output = ""
        for item in results["workers"]:
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
