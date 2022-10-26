#!/usr/bin/env python3

# drains host (quarantines and wait for jobs to finish), runs a command, and then lifts the quarantine

# takes same args as quarantine-tool

import argparse
import re
import subprocess
import sys
import time

from worker_health import quarantine, status


def natural_sort_key(s, _nsre=re.compile("([0-9]+)")):
    return [int(text) if text.isdigit() else text.lower() for text in _nsre.split(s)]


def csv_strs(vstr, sep=","):
    """Convert a string of comma separated values to strings
    @returns iterable of strings
    """
    values = []
    for v0 in vstr.split(sep):
        try:
            v = str(v0)
            values.append(v)
        except ValueError as err:
            raise argparse.ArgumentError(
                "Invalid value %s, values must be a number (%s)" % (vstr, err)
            )
    return values


# uses os x speech api
def say(what_to_say):
    subprocess.run(f"say '{what_to_say}' &", shell=True)


class SafeRunner:
    default_fqdn_postfix = ".test.releng.mdc1.mozilla.com"

    def __init__(self, provisioner, worker_type, fqdn_prefix=default_fqdn_postfix):
        self.provisioner = provisioner
        self.worker_type = worker_type

        # TODO: take as an arg
        self.fqdn_postfix = fqdn_prefix

        self.si = status.Status(provisioner, worker_type)
        self.q = quarantine.Quarantine()

    # TODO: have a multi-host with smarter sequencing...
    #   - for large groups of hosts, quarantine several at a time?

    def safe_run_single_host(self, hostname, command, verbose=True, talk=False):
        # TODO: ensure command has SR_HOST variable in it

        # quarantine
        if verbose:
            print(f"{hostname}: adding to quarantine...")
        # TODO: make this silent
        self.q.quarantine(self.provisioner, self.worker_type, [hostname], verbose=False)
        # TODO: verify?
        if verbose:
            print(f"{hostname}: quarantined.")
            if talk:
                say("quarantined")

        # wait until drained (not running jobs)
        # TODO: where to get the fqdn? our input is only hostname...
        if verbose:
            print(f"{hostname}: waiting for host to drain...")
            if talk:
                say("draining")
        self.si.wait_until_no_jobs_running([hostname])
        if verbose:
            print(f"{hostname}: drained.")
            if talk:
                say("drained")

        # TODO: check that nz is present first
        # if we waited, the host just finished a job and is probably rebooting, so
        # wait for host to be back up, otherwise ssh will time out.
        up_check_cmd = f"nc -z {hostname}{self.fqdn_postfix} 22"
        if verbose:
            print(f"{hostname}: waiting for ssh on host to be responsive...")
        while True:
            spr = subprocess.run(up_check_cmd, shell=True)
            rc = spr.returncode
            if rc == 0:
                break
            time.sleep(2)
        if verbose:
            print(f"{hostname}: ssh is responsive.")
            if talk:
                subprocess.run("host is up", shell=True)

        # run command
        custom_cmd = command.replace("SR_HOST", hostname)
        if verbose:
            print(f"{hostname}: running command '{custom_cmd}'...")
        split_custom_cmd = ["/bin/bash", "-l", "-c", custom_cmd]
        ro = subprocess.run(
            split_custom_cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE
        )
        rc = ro.returncode

        print("")
        output = ro.stdout.decode()
        for line in output.strip().split("\n"):
            print(line)
        print("")

        if rc != 0:
            print(f"{hostname}: command failed. exiting...")
            if talk:
                say("failure")
            sys.exit(1)
        if verbose:
            print(f"{hostname}: command completed successfully.")
            if talk:
                say("converted")

        # lift quarantine
        if verbose:
            print(f"{hostname}: lifting quarantine...")
        self.q.lift_quarantine(self.provisioner, self.worker_type, [hostname])
        # TODO: verify?
        if verbose:
            print(f"{hostname}: quarantine lifted.")
            if talk:
                say("quarantine lifted")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="runs a command against a set of hosts once they are quarantined and not working"
    )
    parser.add_argument(
        "--talk",
        "-t",
        action="store_true",
        help="use OS X's speech API to give updates",
    )
    parser.add_argument(
        "--fqdn-postfix",
        "-f",
        help=(
            f"string to append to host (used for ssh check). defaults to '{SafeRunner.default_fqdn_postfix}'."
        ),
    )
    parser.add_argument("provisioner", help="e.g. 'releng-hardware' or 'gecko-t'")
    parser.add_argument("worker_type", help="e.g. 'gecko-t-osx-1015-r8'")
    parser.add_argument("host_csv", type=csv_strs, help="e.g. 'host1,host2'")
    parser.add_argument("command", help="command to run locally")
    args = parser.parse_args()
    args.hosts = args.host_csv

    # print(args)
    # sys.exit(0)

    sr = SafeRunner(args.provisioner, args.worker_type)

    if args.talk:
        say("SR talk enabled")

    # get user to ack what we're about to do
    print("about to do the following:")
    print(f"  provisioner: {args.provisioner}")
    print(f"  worker_type: {args.worker_type}")
    print(f"  hosts ({len(args.hosts)}): {args.hosts}")
    print(f"  command: {args.command}")
    print("")
    print("type 'yes' to continue: ", end="")
    user_input = input()
    if user_input != "yes":
        print("user chose to exit")
        sys.exit(0)

    host_total = len(args.hosts)
    counter = 0
    for host in args.hosts:
        counter += 1
        if args.talk:
            subprocess.run(f"say SR: starting {host}", shell=True)
        print(f"*** {counter}/{host_total}: {host}")
        sr.safe_run_single_host(host, args.command, talk=args.talk)
    if args.talk:
        subprocess.run(f"say SR: completed {host}", shell=True)
