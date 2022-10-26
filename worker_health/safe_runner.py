#!/usr/bin/env python3

# drains host (quarantines and wait for jobs to finish), runs a command, and then lifts the quarantine

# takes same args as quarantine-tool

import argparse
import datetime
import re
import subprocess
import sys
import time

from worker_health import quarantine, status, utils

# TODO: progress/state tracking
#   - how to do? just ignore that commands could change between commands initially... let users handle
#   - statefile name 'sr_state', TOML
#      - will have all run details and state
#   - contents: current host, completed hosts
#   - where: place in sr_directory... to resume, pass in that directory


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
def say(what_to_say, background_mode=False):
    cmd_to_run = f"say '{what_to_say}'"
    if background_mode:
        cmd_to_run += " &"
    subprocess.run(cmd_to_run, shell=True)


def status_print(line_to_print):
    ctime = datetime.datetime.now()
    ctime_str = ctime.strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ctime_str}: {line_to_print}")


class SafeRunner:
    default_fqdn_postfix = ".test.releng.mdc1.mozilla.com"

    def __init__(self, provisioner, worker_type, fqdn_prefix=default_fqdn_postfix):
        self.provisioner = provisioner
        self.worker_type = worker_type
        self.fqdn_postfix = fqdn_prefix

        # for writing logs to a consistent dated dir
        self.start_datetime = datetime.datetime.now()

        self.si = status.Status(provisioner, worker_type)
        self.q = quarantine.Quarantine()

    @property
    def output_dirname(self):
        datetime_format_for_directory = "%Y%m%d-%H%M%S"
        datetime_part = self.start_datetime.strftime(datetime_format_for_directory)
        return f"sr_{datetime_part}"

    # TODO: have a multi-host with smarter sequencing...
    #   - for large groups of hosts, quarantine several at a time?
    def safe_run_single_host(self, hostname, command, verbose=True, talk=False):
        # TODO: ensure command has SR_HOST variable in it

        # quarantine
        # TODO: check if already quarantined and skip if so
        if verbose:
            status_print(f"{hostname}: adding to quarantine...")
        self.q.quarantine(self.provisioner, self.worker_type, [hostname], verbose=False)
        # TODO: verify?
        if verbose:
            status_print(f"{hostname}: quarantined.")
            if talk:
                say("quarantined")

        # wait until drained (not running jobs)
        if verbose:
            # TODO: show link to tc page
            #  - https://firefox-ci-tc.services.mozilla.com/provisioners/releng-hardware/worker-types/gecko-t-osx-1015-r8/workers/mdc1/macmini-r8-12?sortBy=started&sortDirection=desc
            # wgs = tc_helpers.get_worker_groups(
            #             provisioner=provisioner_id, worker_type=worker_type
            #         )

            status_print(f"{hostname}: waiting for host to drain...")
            if talk:
                say("draining")
        self.si.wait_until_no_jobs_running([hostname])
        if verbose:
            status_print(f"{hostname}: drained.")
            if talk:
                say("drained")

        # TODO: check that nc is present first
        # if we waited, the host just finished a job and is probably rebooting, so
        # wait for host to be back up, otherwise ssh will time out.
        up_check_cmd = f"nc -z {hostname}{self.fqdn_postfix} 22"
        if verbose:
            status_print(f"{hostname}: waiting for ssh on host to be responsive...")
            if talk:
                say("waiting for ssh")
        while True:
            spr = subprocess.run(up_check_cmd, shell=True)
            rc = spr.returncode
            if rc == 0:
                break
            time.sleep(2)
        if verbose:
            status_print(f"{hostname}: ssh is responsive.")

        # run command
        custom_cmd = command.replace("SR_HOST", hostname)
        if verbose:
            status_print(f"{hostname}: running command '{custom_cmd}'...")
            if talk:
                say("converging")
        split_custom_cmd = ["/bin/bash", "-l", "-c", custom_cmd]
        ro = subprocess.run(
            split_custom_cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE
        )
        rc = ro.returncode
        output = ro.stdout.decode()

        # write output to a file per host in a directory for the run
        header = ""
        header += "# safe_runner output'\n"
        header += "#'\n"
        header += f"# provisioners: '{self.provisioner}'\n"
        header += f"# worker_type: '{self.worker_type}'\n"
        header += f"# hostname: '{hostname}'\n"
        header += f"# run datetime: '{self.start_datetime}'\n"
        header += f"# command run: '{custom_cmd}'\n"
        header += f"# exit code: {rc}\n"
        file_output = f"{header}#\n{output}"
        utils.mkdir_p(self.output_dirname)
        with open(f"{self.output_dirname}/{hostname}.txt", "w") as out:
            out.write(file_output)

        print("")
        for line in output.strip().split("\n"):
            print(line)
        print("")

        if rc != 0:
            status_print(
                f"{hostname}: command failed. host is still quarantined. exiting..."
            )
            if talk:
                say("failure")
            sys.exit(1)
        if verbose:
            status_print(f"{hostname}: command completed successfully.")
            if talk:
                say("converged")

        # lift quarantine
        if verbose:
            status_print(f"{hostname}: lifting quarantine...")
        self.q.lift_quarantine(self.provisioner, self.worker_type, [hostname])
        # TODO: verify?
        if verbose:
            status_print(f"{hostname}: quarantine lifted.")
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
    # TODO: add as real option?
    args.pre_quarantine = True
    args.verbose = True
    args.pre_quarantine_additional_host_count = 2

    # print(args)
    # sys.exit(0)

    sr = SafeRunner(args.provisioner, args.worker_type)

    if args.talk:
        say("SR talk enabled", background_mode=True)

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

    # TODO: eventually use this as outer code for safe_run_multi_host
    # TODO: add 'quarantine ahead' feature
    #   - currently we end up waiting a long time for drain
    host_total = len(args.hosts)
    counter = 0
    for host in args.hosts:
        counter += 1

        # pre-quarantine code
        #   - gets a few workers ready (quarantined) before we're working on them
        if args.pre_quarantine:
            pre_quarantine_hosts = utils.arr_get_followers(
                args.hosts, host, args.pre_quarantine_additional_host_count
            )
            if args.verbose:
                status_print(
                    f"pre-quarantine: adding to quarantine: {pre_quarantine_hosts}"
                )
            sr.q.quarantine(
                args.provisioner, args.worker_type, pre_quarantine_hosts, verbose=False
            )
            if args.verbose:
                status_print(f"pre-quarantine: added {len(pre_quarantine_hosts)} hosts")
                if args.talk:
                    say(f"pre-quarantined {len(pre_quarantine_hosts)} hosts")

        # safe_run_single_host
        if args.talk:
            say(f"SR: starting {host}")
        status_print(f"*** {counter}/{host_total}: {host}")
        sr.safe_run_single_host(host, args.command, talk=args.talk)
        if args.talk:
            say(f"SR: completed {host}")
        print("")
