#!/usr/bin/env python

import argparse
import pprint

from worker_health import quarantine

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "provisioner",
        help="e.g. 'TC provisioner, terraform-packet' or 'releng-hardware'",
    )
    parser.add_argument(
        "worker_type",
        help="e.g. 'TC worker_type, gecko-t-bitbar-gw-perf-p2.pixel2-21' or 'gecko-t-bitbar-gw-batt-g5'",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        dest="verbose",
        default=0,
        help="specify multiple times for even more verbosity",
    )
    # display all workers in worker_type, for displaying hostnames to quarantine
    parser.add_argument("--show-all", "-s", action="store_true")
    args = parser.parse_args()
    # pprint.pprint(args)
    provisioner = args.provisioner
    worker_type = args.worker_type

    q = quarantine.Quarantine()

    if args.show_all:
        results = q.get_workers(provisioner, worker_type)
        for r in results["workers"]:
            print(r["workerId"])
    else:
        # TODO: check if worker_type is valid somehow
        quarantined_workers = q.get_quarantined_workers(provisioner, worker_type)
        if args.verbose:
            print("%s/%s" % (provisioner, worker_type))
        if args.verbose >= 2:
            print(
                "  %s/provisioners/%s/worker-types/%s"
                % (q.root_url, provisioner, worker_type)
            )
        pprint.pprint(quarantined_workers)

        # vestigial?
        # q.main_get_quarantined()
