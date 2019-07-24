#!/usr/bin/env python3

import argparse

import worker_health


def main():

    # TODO: catch ctrl-c and exit nicely

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        default=False,
        help="list all worker-types on TC even if not missing workers",
    )
    parser.add_argument(
        "-u",
        "--update",
        action="store_true",
        default=False,
        help="force an update to the devicepool repository (normally updated every %s seconds)"
        % worker_health.REPO_UPDATE_SECONDS,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        dest="log_level",
        default=0,
        help="specify multiple times for even more verbosity",
    )
    parser.add_argument(
        "-t",
        "--time-limit",
        type=int,
        default=60,
        help="for tc, devices are missing if not reporting for longer than this many minutes. defaults to 60.",
    )
    args = parser.parse_args()
    wh = worker_health.WorkerHealth(args.log_level)

    # TESTING
    # output = wh.get_jsonc("https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types/gecko-t-ap-unit-p2/workers?limit=50")
    # wh.pp.pprint(output)
    # sys.exit(0)

    wh.show_report(args.all, args.time_limit, args.influx_logging, args.log_level)


if __name__ == "__main__":
    main()
