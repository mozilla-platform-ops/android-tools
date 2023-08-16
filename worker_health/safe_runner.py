#!/usr/bin/env python3

# drains host (quarantines and wait for jobs to finish),
#   runs a command, and then lifts the quarantine

import argparse

from worker_health import runner

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=("runs a command against a set of hosts once " "they are quarantined and not working")
    )
    parser.add_argument(
        "--resume_dir",
        "-r",
        metavar="RUN_DIR",
        # custom action that removes the positional args
        action=runner.ResumeAction,
        help="'sr_' run directory. causes positional arguments to be ignored.",
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
        "--dont-lift_quarantine",
        "-D",
        action="store_true",
        help=("don't lift the quarantine after successfully running. " "useful for pre-quarantined bad hosts."),
    )
    # TODO: add argument to do a reboot if run is successful?
    parser.add_argument(
        "--fqdn-postfix",
        "-F",
        help=("string to append to host (used for ssh check). " f"defaults to '{runner.Runner.default_fqdn_postfix}'."),
    )
    parser.add_argument(
        "--pre_quarantine_additional_host_count",
        "-P",
        help=(
            "quarantine the specified number of following hosts. "
            f"defaults to {runner.Runner.default_pre_quarantine_additional_host_count}. "
            "specify 0 to disable pre-quarantine."
        ),
        metavar="COUNT",
        type=int,
        default=runner.Runner.default_pre_quarantine_additional_host_count,
    )
    # positional args
    parser.add_argument("provisioner", help="e.g. 'releng-hardware' or 'gecko-t'")
    parser.add_argument("worker_type", help="e.g. 'gecko-t-osx-1015-r8'")
    parser.add_argument("host_csv", type=runner.csv_strs, help="e.g. 'host1,host2'")
    parser.add_argument("command", help="command to run locally")
    args = parser.parse_args()
    args.hosts = args.host_csv
    # TODO: add as an exposed option?
    args.verbose = True

    runner.main(args, safe_mode=True)
