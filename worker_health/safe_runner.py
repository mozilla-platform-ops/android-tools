#!/usr/bin/env python3

# drains host (quarantines and wait for jobs to finish), runs a command, and then lifts the quarantine

import argparse
import copy
import datetime
import os
import re
import signal
import subprocess
import sys
import time

import colorama
import tomlkit

from worker_health import quarantine, status, utils

# TODO: progress/state tracking
#   - how to do? just ignore that commands could change between commands initially... let users handle
#   - statefile name 'sr_state', TOML
#      - will have all run details and state
#   - contents: current host, completed hosts
#   - where: place in sr_directory... to resume, pass in that directory


# TODO: move these non-class functions to utils?


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
            raise Exception(
                "Invalid value %s, values must be a number (%s)" % (vstr, err)
            )
    return values


# uses os x speech api
def say(what_to_say, background_mode=False):
    # Samantha is the Siri voice, default is System setting
    cmd_to_run = f"say -v Samantha '{what_to_say}'"
    if background_mode:
        cmd_to_run += " &"
    subprocess.run(cmd_to_run, shell=True)


def status_print(line_to_print, end="\n"):
    ctime = datetime.datetime.now()
    ctime_str = ctime.strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ctime_str}: {line_to_print}", end=end, flush=True)


def preexec_function():
    # Ignore the SIGINT signal by setting the handler to the standard
    # signal handler SIG_IGN.
    signal.signal(signal.SIGINT, signal.SIG_IGN)


class SafeRunner:
    default_pre_quarantine_additional_host_count = 5
    default_fqdn_postfix = ".test.releng.mdc1.mozilla.com"
    state_file_name = "sr_state.toml"
    # TODO: use tomlkit tables so formatting is nice for empty lists?
    empty_config_dict = {
        "config": {
            "provisioner": "",
            "worker_type": "",
            "command": "",
            "hosts_to_skip": [],
        },
        "state": {
            "remaining_hosts": [],
            "completed_hosts": [],
        },
    }

    def __init__(
        self,
        provisioner,
        worker_type,
        hosts,
        command,
        fqdn_prefix=default_fqdn_postfix,
    ):
        # required args
        self.provisioner = provisioner
        self.worker_type = worker_type
        self.command = command
        # optional args
        self.fqdn_postfix = fqdn_prefix

        # TODO: should we store this? so write will preserve comments?
        # self._config_toml = {}
        # state
        self.completed_hosts = []
        self.remaining_hosts = hosts

        # instances
        self.si = status.Status(provisioner, worker_type)
        self.q = quarantine.Quarantine()

        # for writing logs to a consistent dated dir
        self.start_datetime = datetime.datetime.now()
        self.run_dir = self.default_rundir_path
        self.state_file = self.default_state_file_path

    # alternate constructor
    @classmethod
    def from_resume(cls, resume_dir):
        # open file and read
        resume_file = f"{resume_dir}/{SafeRunner.state_file_name}"

        # load file
        #
        # tomli
        # with open(resume_file, "rb") as f:
        # data = toml_reader.load(f)
        #
        # tomlkit
        with open(resume_file, "rb") as f:
            data = tomlkit.load(f)
        #
        # print(data)

        # sanity check
        try:
            data["state"]
            data["config"]
        except tomlkit.exceptions.NonExistentKey:
            raise Exception(f"invalid file format in '{resume_file}'")

        # filter out skipped hosts
        # TODO: 'hosts_to_skip' is pretty silly, just removes hosts from remaining_hosts...
        # remaining_hosts_without_hosts_to_skip = []
        # mutate this because it's a special tomlkit datastructure (preserves formatting)
        for h in data["state"]["remaining_hosts"]:
            if h in data["config"]["hosts_to_skip"]:
                data["state"]["remaining_hosts"].remove(h)
                # remaining_hosts_without_hosts_to_skip.append(h)

        # create class with minimum params
        i = cls(
            data["config"]["provisioner"],
            data["config"]["worker_type"],
            data["state"]["remaining_hosts"],
            data["config"]["command"],
        )
        # populate rest
        i.completed_hosts = data["state"]["completed_hosts"]
        i.run_dir = resume_dir
        i.state_file = f"{resume_dir}/{SafeRunner.state_file_name}"
        return i

    @property
    def default_rundir_path(self):
        datetime_format_for_directory = "%Y%m%d-%H%M%S"
        datetime_part = self.start_datetime.strftime(datetime_format_for_directory)
        return f"sr_{datetime_part}"

    @property
    def default_state_file_path(self):
        return f"{self.default_rundir_path}/{SafeRunner.state_file_name}"

    # TODO: use tomlkit?
    #   - we can have comment-like metadata fields that we don't have to load/save
    #     - (pre_)quarantined hosts
    #     - original hosts: otherwise we lose this data?
    #       - hm, can add completed and remaining (but what if user modifies?)
    #     - completed hosts is currently in class, but not used (just metadata)
    #     - what else?
    def write_initial_toml(self):
        # populate data
        data = copy.deepcopy(SafeRunner.empty_config_dict)
        # config
        data["config"]["provisioner"] = self.provisioner
        data["config"]["worker_type"] = self.worker_type
        data["config"]["command"] = self.command
        # not writing hosts_to_skip
        # state
        data["state"]["remaining_hosts"] = self.remaining_hosts
        # not writing remaining

        utils.mkdir_p(os.path.dirname(self.state_file))
        # tomli_w
        # toml_output = toml_writer.dumps(data)
        # with open(self.state_file, "w") as out:
        #     out.write(toml_output)
        # tomlkit
        tomlkit.dump(self.state_file, data)

    # loads existing state file first, so we can preserve comments
    def checkpoint_toml(self):
        with open(self.state_file, "r") as f:
            data = tomlkit.load(f)

        # update data
        data["state"]["completed_hosts"] = self.completed_hosts
        data["state"]["remaining_hosts"] = self.remaining_hosts

        # write
        with open(self.state_file, "w") as f:
            tomlkit.dump(data, f)

    # TODO: have a multi-host with smarter sequencing...
    #   - for large groups of hosts, quarantine several at a time?
    def safe_run_single_host(self, hostname, command, verbose=True, talk=False):
        # TODO: ensure command has SR_HOST variable in it
        if "SR_HOST" not in command:
            raise Exception("command doesn't have SR_HOST in it!")

        # quarantine
        # TODO: check if already quarantined and skip if so
        if verbose:
            status_print(f"{hostname}: adding to quarantine... ", end="")
        self.q.quarantine(self.provisioner, self.worker_type, [hostname], verbose=False)
        # TODO: verify?
        if verbose:
            print("quarantined.")
            if talk:
                say("quarantined")

        # wait until drained (not running jobs)
        if verbose:
            # TODO: show link to tc page
            #  - https://firefox-ci-tc.services.mozilla.com/provisioners/releng-hardware/worker-types/gecko-t-osx-1015-r8/workers/mdc1/macmini-r8-12?sortBy=started&sortDirection=desc
            # wgs = tc_helpers.get_worker_groups(
            #             provisioner=provisioner_id, worker_type=worker_type
            #         )

            status_print(f"{hostname}: waiting for host to drain...", end="")
            if talk:
                say("draining")
        self.si.wait_until_no_jobs_running([hostname])
        if verbose:
            print(" drained.")
            if talk:
                say("drained")

        # TODO: check that nc is present first
        # if we waited, the host just finished a job and is probably rebooting, so
        # wait for host to be back up, otherwise ssh will time out.
        if verbose:
            status_print(f"{hostname}: waiting for ssh to be up... ", end="")
            if talk:
                say("waiting for ssh")
        while True:
            host_fqdn = f"{hostname}{self.fqdn_postfix}"
            if host_is_sshable(host_fqdn):
                break
            time.sleep(5)
        if verbose:
            print("ready.")

        # run `ssh-keygen -R` and `ssh-keyscan -t rsa` and update our known_hosts
        # TODO: put behind flag?
        # TODO: mention we're doing this?
        host_fqdn = f"{hostname}{self.fqdn_postfix}"
        cmd = f"ssh-keygen -R {host_fqdn}"
        subprocess.run(
            cmd,
            shell=True,
            check=True,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
        )
        cmd = f"ssh-keyscan -t rsa {host_fqdn} >> ~/.ssh/known_hosts"
        subprocess.run(
            cmd,
            shell=True,
            check=True,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
        )

        # run command
        custom_cmd = command.replace("SR_HOST", hostname)
        if verbose:
            status_print(f"{hostname}: running command '{custom_cmd}'...")
            if talk:
                say("converging")
        split_custom_cmd = ["/bin/bash", "-l", "-c", custom_cmd]
        ro = subprocess.run(
            split_custom_cmd,
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,
            # process should ignore parent ctrl-c
            preexec_fn=lambda: preexec_function,
        )
        rc = ro.returncode
        output = ro.stdout.decode()

        # write output to a file per host in a directory for the run
        header = ""
        header += "# safe_runner output \n"
        header += "# \n"
        header += f"# provisioners: '{self.provisioner}' \n"
        header += f"# worker_type: '{self.worker_type}' \n"
        header += f"# hostname: '{hostname}' \n"
        header += f"# run datetime: '{self.start_datetime}' \n"
        header += f"# command run: '{custom_cmd}' \n"
        header += f"# exit code: {rc} \n"
        # TODO: add skipped hosts?
        file_output = f"{header}#\n{output}\n"
        utils.mkdir_p(self.run_dir)
        with open(f"{self.run_dir}/{hostname}.txt", "a") as out:
            out.write(file_output)

        print(colorama.Style.DIM, end="")
        for line in output.strip().split("\n"):
            print(f"  {line}")
        print(colorama.Style.RESET_ALL, end="")

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
            status_print(f"{hostname}: lifting quarantine...", end="")
        self.q.lift_quarantine(
            self.provisioner, self.worker_type, [hostname], verbose=False
        )
        # TODO: verify?
        if verbose:
            print(" lifted.")
            if talk:
                say("quarantine lifted")


def remove_argument(parser, arg):
    for action in parser._actions:
        # print(action)
        opts = action.option_strings
        if (opts and opts[0] == arg) or action.dest == arg:
            parser._remove_action(action)
            break

    for action in parser._action_groups:
        # print(action)
        for group_action in action._group_actions:
            if group_action.dest == arg:
                action._group_actions.remove(group_action)
                return


class ResumeAction(argparse.Action):
    def __call__(self, parser, args, values, option_string):
        # remove these arguments becuase they're not needed with -r/--resume_file
        remove_argument(parser, "provisioner")
        remove_argument(parser, "worker_type")
        remove_argument(parser, "command")
        remove_argument(parser, "host_csv")
        # the normal part
        setattr(args, self.dest, values)


def handler(_signum, _frame):
    global terminate
    terminate += 1
    print("")
    if terminate >= 2:
        print("*** double ctrl-c detected. exiting immediately!")
        sys.exit(0)
    print(
        "*** ctrl-c detected. will exit at end of current host (another will exit immediately)."
    )


# given a string hostname, returns True if sshable, else False.
def host_is_sshable(hostname):
    up_check_cmd = f"nc -w 2 -G 3 -z {hostname} 22 2>&1"
    spr = subprocess.run(
        up_check_cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, shell=True
    )
    rc = spr.returncode
    if rc == 0:
        return True
    return False


def print_banner():
    # from `figlet -f smslant safe runner`
    # looks strange as first line is indented
    print(
        colorama.Style.BRIGHT
        + """            ___
  ___ ___ _/ _/__   ______ _____  ___  ___ ____
 (_-</ _ `/ _/ -_) / __/ // / _ \/ _ \/ -_) __/
/___/\_,_/_/ \__/ /_/  \_,_/_//_/_//_/\__/_/
"""  # noqa: W605
        + colorama.Style.RESET_ALL
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="runs a command against a set of hosts once they are quarantined and not working"
    )
    parser.add_argument(
        "--resume_dir",
        "-r",
        metavar="RUN_DIR",
        action=ResumeAction,
        help="'sr_' run directory. causes positional arguments to be ignored.",
    )
    parser.add_argument(
        "--talk",
        "-t",
        action="store_true",
        help="use OS X's speech API to give updates",
    )
    parser.add_argument(
        "--fqdn-postfix",
        "-F",
        help=(
            f"string to append to host (used for ssh check). defaults to '{SafeRunner.default_fqdn_postfix}'."
        ),
    )
    parser.add_argument(
        "--pre_quarantine_additional_host_count",
        "-P",
        help=f"quarantine the specified number of following hosts. defaults to {SafeRunner.default_pre_quarantine_additional_host_count}. specify 0 to disable pre-quarantine.",
        metavar="COUNT",
        type=int,
        default=SafeRunner.default_pre_quarantine_additional_host_count,
    )
    parser.add_argument("provisioner", help="e.g. 'releng-hardware' or 'gecko-t'")
    parser.add_argument("worker_type", help="e.g. 'gecko-t-osx-1015-r8'")
    parser.add_argument("host_csv", type=csv_strs, help="e.g. 'host1,host2'")
    parser.add_argument("command", help="command to run locally")
    args = parser.parse_args()
    args.hosts = args.host_csv
    # TODO: add as an exposed option?
    args.verbose = True

    print_banner()

    # print(args)
    # sys.exit(0)

    if args.talk:
        say("safe runner: talk enabled", background_mode=True)

    if not args.resume_dir:
        # fresh start: write out toml file
        # print("no resume")
        sr = SafeRunner(args.provisioner, args.worker_type, args.hosts, args.command)
    else:
        # handle resume: load file
        # print("resume passed in")
        sr = SafeRunner.from_resume(args.resume_dir)

    # get user to ack what we're about to do
    # TODO: mention skipped hosts?
    print("Run options:")
    print(f"  provisioner: {sr.provisioner}")
    print(f"  worker_type: {sr.worker_type}")
    print(f"  hosts ({len(sr.remaining_hosts)}): {', '.join(sr.remaining_hosts)}")
    print(f"  command: {sr.command}")
    print("")
    print("Does this look correct? Type 'yes' to proceed: ", end="")
    user_input = input()
    if user_input != "yes":
        print("user chose to exit")
        sys.exit(0)
    print("")

    # TODO: ideally this would just be when we're converging until done
    signal.signal(signal.SIGINT, handler)

    # for fresh runs, write toml
    if not args.resume_dir:
        sr.write_initial_toml()

    # TODO: eventually use this as outer code for safe_run_multi_host
    # TODO: make a more-intelligent multi-host version...
    #   - this will wait on current host if not drained (when other hosts in pre-quarantine group are ready)
    host_total = len(sr.remaining_hosts)
    counter = 0
    global terminate
    terminate = 0
    while sr.remaining_hosts:
        counter += 1

        # pre-quarantine code
        #   - gets a few workers ready (quarantined) before we're working on them
        pre_quarantine_hosts = sr.remaining_hosts[
            0 : (args.pre_quarantine_additional_host_count + 1)
        ]
        if args.pre_quarantine_additional_host_count:
            status_print(
                f"pre-quarantine: adding to quarantine: {pre_quarantine_hosts}"
            )
            sr.q.quarantine(
                sr.provisioner, sr.worker_type, pre_quarantine_hosts, verbose=False
            )
            status_print(
                f"pre-quarantine: quarantined {len(pre_quarantine_hosts)} hosts"
            )
            if args.talk:
                say(f"pre-quarantined {len(pre_quarantine_hosts)} hosts")

            # waits for a host that isn't running jobs
            # status_print("waiting for idle pre-quarantined host...")
            # host = sr.si.wait_for_idle_host(pre_quarantine_hosts)
            #
            # waits for a host that isn't running jobs and ssh-able
            status_print(
                "waiting for pre-quarantined host that is idle and ssh-able... "  # , end=""
            )
            exit_while = False
            while True:
                # print("0", end="", flush=True)
                status_print("waiting for idle hosts among pre-quarantined... ", end="")
                idle_hosts = sr.si.wait_for_idle_hosts(
                    pre_quarantine_hosts, show_indicator=True
                )
                status_print(f"hosts found: {', '.join(idle_hosts)}.")
                for i_host in idle_hosts:
                    # print(".", end="", flush=True)
                    i_host_fqdn = f"{i_host}{sr.fqdn_postfix}"
                    status_print(f"checking for ssh: {i_host_fqdn}...")
                    if host_is_sshable(i_host_fqdn):
                        host = i_host
                        exit_while = True
                        break
                if exit_while:
                    break
                # print("Z", end="", flush=True)
                status_print("no quarantined idle ssh-able hosts found. sleeping...")
                time.sleep(60)
            # print(" found.", flush=True)
        else:
            host = sr.remaining_hosts[0]

        # safe_run_single_host
        status_print(f"{host}: starting")
        if args.talk:
            say(f"starting {host}")
        sr.safe_run_single_host(host, sr.command, talk=args.talk)
        sr.remaining_hosts.remove(host)
        status_print(f"{host}: complete")
        status_print(
            f"hosts remaining ({len(sr.remaining_hosts)}/{host_total}): {', '.join(sr.remaining_hosts)}"
        )
        if args.talk:
            say(f"completed {host}.")
            say(f"{len(sr.remaining_hosts)} of {host_total} hosts remaining.")
        sr.completed_hosts.append(host)
        sr.checkpoint_toml()
        if terminate > 0:
            status_print("graceful exiting...")
            # TODO: show quarantined hosts?
            break
        # TODO: play success sound
        # TODO: can we show any stats?
        # status_print("all hosts complete!")
