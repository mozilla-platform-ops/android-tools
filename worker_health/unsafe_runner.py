#!/usr/bin/env python3

# runs a command with checkpoint
# - if you need to quarantine hosts, use safe_runner (this is not safe)

import argparse

from worker_health import runner

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=("runs a command against a set of hosts"))
    parser.add_argument(
        "--resume_dir",
        "-r",
        metavar="RUN_DIR",
        # custom action that removes the positional args
        action=runner.ResumeAction,
        help="causes positional arguments to be ignored. recommend prefixing with 'ur_' if not pre-existing.",
    )
    parser.add_argument(
        "--do-not-randomize",
        "-N",
        action="store_true",
        help="don't randomize host list",
    )
    parser.add_argument(
        "--talk",
        "-t",
        action="store_true",
        help="use OS X's speech API to give updates",
    )
    parser.add_argument(
        "--reboot-host",
        "-R",
        action="store_true",
        help="reboot the host after command runs successfully.",
    )
    # TODO: add argument to do a reboot if run is successful?
    parser.add_argument(
        "--fqdn-postfix",
        "-F",
        help=("string to append to host (used for ssh check). " f"defaults to '{runner.Runner.default_fqdn_postfix}'."),
    )
    # positional args
    parser.add_argument("host_csv", type=runner.csv_strs, help="e.g. 'host1,host2'")
    parser.add_argument("command", help="command to run locally")
    args = parser.parse_args()
    args.hosts = args.host_csv
    # TODO: add as an exposed option?
    args.verbose = True
    args.dont_lift_quarantine = True

    runner.main(args)
