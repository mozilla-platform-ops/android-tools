#!/usr/bin/env python3

from worker_health import quarantine

if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("provisioner")
    parser.add_argument("worker_type")
    parser.add_argument(
        "action",
        choices=["lift", "quarantine", "show", "show-all"],
        help="action to do",
    )
    parser.add_argument("action_options", nargs="?")

    # group = parser.add_argument_group('actions')
    # mxg = group.add_mutually_exclusive_group(required=True)

    # mxg.add_argument("-l", "--lift", action="store_true", help="lift the quarantine")
    # mxg.add_argument("-q", "--quarantine", action="store_true")
    # mxg.add_argument("-g", "--get-quarantined", action="store_true")
    # mxg.add_argument("-a", "--get-all", action="store_true")

    # parser.add_argument("-p", "--pool", required=True)

    args = parser.parse_args()

    if args.action == "quarantine":
        q = quarantine.Quarantine()
        pass
    elif args.action == "lift":
        if args.action_options is None:
            parser.error("you must specify a csv of hosts")
        host_arr = args.action_options.split(",")
        q = quarantine.Quarantine()
        q.lift_quarantine(
            provisioner=args.provisioner,
            worker_type=args.worker_type,
            device_arr=host_arr,
        )
    elif args.action == "show":
        q = quarantine.Quarantine()
        results = q.get_quarantined_workers(
            provisioner=args.provisioner, worker_type=args.worker_type
        )
        print("workerId")
        for r in results:
            print(r)
    elif args.action == "show-all":
        q = quarantine.Quarantine()
        results = q.get_workers(args.provisioner, args.worker_type)
        print("workerGroup,workerId")
        for item in results["workers"]:
            print("%s,%s" % (item["workerGroup"], item["workerId"]))
    else:
        parser.error("please specify an action")
