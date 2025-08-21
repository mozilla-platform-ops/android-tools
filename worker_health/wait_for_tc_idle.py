#!/usr/bin/env python

# waits for the hosts passed in to be idle
# - have a mode that exits on one or all
#
# example usage:
#   ./wait_for_tc_idle.py \
#     -p releng-hardware -w gecko-t-linux-talos-1804 \
#     t-linux64-ms-239,t-linux64-ms-240 -v

import argparse
import time
from worker_health import status


def main():
    parser = argparse.ArgumentParser(description="Wait for specified hosts to be idle.")
    parser.add_argument("--provisioner", "-p", required=True, help="Provisioner name (e.g., releng-hardware)")
    parser.add_argument("--worker-type", "-w", required=True, help="Worker type (e.g., gecko-t-linux-talos-1804)")
    parser.add_argument("hosts", nargs="+", help="List of hostnames to check")
    # add a --single argument, that enables a mode that exits when any node is idle
    parser.add_argument(
        "--single",
        "-s",
        action="store_true",
        help="Exit when any node is idle (vs default when all are idle)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    args = parser.parse_args()

    si = status.Status(args.provisioner, args.worker_type)
    hosts_with_non_completed_or_failed_jobs = si.get_hosts_running_jobs(args.hosts)

    while True:
        # pprint.pprint(hosts_with_non_completed_or_failed_jobs)
        time.sleep(10)
        if args.single:
            # check if any hosts are idle
            input_set = set(args.hosts)
            result_set = set(hosts_with_non_completed_or_failed_jobs)
            difference = input_set - result_set
            if difference:
                if args.verbose:
                    print(f"Hosts no longer busy: {difference}")
                break
            pass
        else:
            # check if all hosts are idle
            if not hosts_with_non_completed_or_failed_jobs:
                if args.verbose:
                    print(f"All hosts are idle: {args.hosts}")
                break


if __name__ == "__main__":
    main()
