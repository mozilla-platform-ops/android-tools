#!/usr/bin/env python3

import sys

from worker_health import quarantine

if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser()

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-l", "--lift", action="store_true", help="lift the quarantine")
    group.add_argument("-q", "--quarantine", action="store_true")
    group.add_argument("-g", "--get-quarantined", action="store_true")

    # parser.add_argument("-p", "--pool", required=True)
    parser.add_argument("-p", "--provisioner", required=True)
    parser.add_argument("-w", "--worker_type", required=True)

    args = parser.parse_args()

    if args.quarantine:
        # cls_instance.quarantine(host_numbers)
        pass
    elif args.lift:
        q = quarantine.Quarantine()
        results = q.get_workers(args.provisioner, args.worker_type)
        for r in results:
            print(r)
    elif args.get_quarantined:
        # print(cls_instance.get_quarantined())
        pass
    else:
        print("please specify an operation")
        sys.exit(1)
