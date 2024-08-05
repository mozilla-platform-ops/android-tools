#!/usr/bin/env python3

# runs a command with checkpoint
# - if you need to quarantine hosts, use safe_runner (this is not safe)

import argparse

from worker_health import runner

VERSION = "2.0.0"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=("runs a command against a set of hosts"))
    parser.add_argument(
        "--resume_dir",
        "-r",
        required=True,
        metavar="RUN_DIR",
        help="recommend prefixing with 'ur_' if not pre-existing.",
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
    parser.add_argument(
        "--reset-state",
        "-S",
        action="store_true",
        help="reset the state section of the config file (all hosts to remaining_hosts)",
    )
    parser.add_argument(
        "--delete-output-files",
        "-D",
        action="store_true",
        help="delete the output files in the state directory",
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {VERSION}")
    args = parser.parse_args()
    # TODO: add as an exposed option?
    args.verbose = True
    args.dont_lift_quarantine = True

    runner.main(args)
