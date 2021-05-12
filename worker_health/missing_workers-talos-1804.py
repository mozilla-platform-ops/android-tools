#!/usr/bin/env python3

import argparse

import fitness
import quarantine

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        dest="log_level",
        default=0,
        help="specify multiple times for even more verbosity.",
    )
    args = parser.parse_args()

    PROVISIONER = "releng-hardware"
    WORKER_TYPE = "gecko-t-linux-talos-1804"

    exclude_arr = [
        "t-linux64-ms-055",  # bad ilo on cart
        "t-linux64-ms-228",  # nvme error
    ]

    # print("not implemented yet")
    # sys.exit(0)

    f = fitness.Fitness(log_level=0, provisioner=PROVISIONER, alert_percent=85)
    q = quarantine.Quarantine()

    q.print_quarantined_workers(PROVISIONER, WORKER_TYPE)
    f.moonshot_worker_report(WORKER_TYPE, args=args, exclude_arr=exclude_arr)


# https://firefox-ci-tc.services.mozilla.com/provisioners/releng-hardware/worker-types/gecko-t-linux-talos-dw
