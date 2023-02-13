#!/usr/bin/env python3

# runs a command with checkpoint
# - if you need to quarantine hosts, use safe_runner (this is not safe)

import argparse
import copy
import datetime
import os
import random
import re
import signal
import subprocess
import sys
import time

import colorama
import tomlkit

from worker_health import utils

# TODO: persist fqdn suffix
# TODO: alive_progress bar
# TODO: command to dump an empty state file in restore dir
# TODO: progress/state tracking
#   - how to do?
#     - just ignore that commands could change between commands initially...
#     - let users handle
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


class UnsafeRunner:
    # default_pre_quarantine_additional_host_count = 5
    default_fqdn_postfix = ".test.releng.mdc1.mozilla.com"
    state_file_name = "ur_state.toml"
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
        hosts,
        command,
        fqdn_prefix=default_fqdn_postfix,
    ):
        # required args
        self.command = command
        # optional args
        self.fqdn_postfix = fqdn_prefix

        # TODO: should we store this? so write will preserve comments?
        # self._config_toml = {}
        # state
        self.completed_hosts = []
        self.remaining_hosts = hosts

        # for writing logs to a consistent dated dir
        self.start_datetime = datetime.datetime.now()
        self.run_dir = self.default_rundir_path
        self.state_file = self.default_state_file_path

    # alternate constructor
    @classmethod
    def from_resume(cls, resume_dir):
        # open file and read
        resume_file = f"{resume_dir}/{UnsafeRunner.state_file_name}"

        # load file
        with open(resume_file, "rb") as f:
            data = tomlkit.load(f)

        # sanity check
        try:
            data["state"]
            data["config"]
        except tomlkit.exceptions.NonExistentKey:
            raise Exception(f"invalid file format in '{resume_file}'")

        # filter out skipped hosts
        # TODO: 'hosts_to_skip' is pretty silly, just removes hosts from
        #   remaining_hosts... mutate this because it's a special tomlkit
        #   datastructure (preserves formatting)
        for h in data["state"]["remaining_hosts"]:
            if h in data["config"]["hosts_to_skip"]:
                data["state"]["remaining_hosts"].remove(h)
                # remaining_hosts_without_hosts_to_skip.append(h)

        # create class with minimum params
        i = cls(
            # data["config"]["provisioner"],
            # data["config"]["worker_type"],
            data["state"]["remaining_hosts"],
            data["config"]["command"],
        )
        # populate rest
        i.completed_hosts = data["state"]["completed_hosts"]
        i.run_dir = resume_dir
        i.state_file = f"{resume_dir}/{UnsafeRunner.state_file_name}"
        return i

    @property
    def default_rundir_path(self):
        datetime_format_for_directory = "%Y%m%d-%H%M%S"
        datetime_part = self.start_datetime.strftime(datetime_format_for_directory)
        return f"sr_{datetime_part}"

    @property
    def default_state_file_path(self):
        return f"{self.default_rundir_path}/{UnsafeRunner.state_file_name}"

    def write_initial_toml(self):
        # populate data
        data = copy.deepcopy(UnsafeRunner.empty_config_dict)
        # config
        data["config"]["provisioner"] = self.provisioner
        data["config"]["worker_type"] = self.worker_type
        data["config"]["command"] = self.command
        # not writing hosts_to_skip
        # state
        data["state"]["remaining_hosts"] = self.remaining_hosts
        # not writing remaining

        utils.mkdir_p(os.path.dirname(self.state_file))
        with open(self.state_file, "w") as f:
            tomlkit.dump(data, f)

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
    def safe_run_single_host(
        self,
        hostname,
        command,
        verbose=True,
        talk=False,
        reboot_host=False,
    ):
        host_fqdn = f"{hostname}{self.fqdn_postfix}"
        # TODO: ensure command has SR_HOST variable in it
        if "SR_HOST" not in command:
            raise Exception("command doesn't have SR_HOST in it!")

        # TODO: check that nc is present first
        # if we waited, the host just finished a job and is probably rebooting, so
        # wait for host to be back up, otherwise ssh will time out.

        if verbose:
            status_print(f"{hostname}: waiting for ssh to be up... ", end="")
        #     if talk:
        #         say("waiting for ssh")
        while True:
            if host_is_sshable(host_fqdn):
                break
            time.sleep(5)
        if verbose:
            print("ready.")

        # run `ssh-keygen -R` and `ssh-keyscan -t rsa` and update our known_hosts
        # TODO: put behind flag?
        # TODO: mention we're removing keys/scanning?
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
                say("running")
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
        # header += f"# provisioners: '{self.provisioner}' \n"
        # header += f"# worker_type: '{self.worker_type}' \n"
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
            status_print(f"{hostname}: command failed.")
            if talk:
                say("failure")
            sys.exit(1)
        if verbose:
            status_print(f"{hostname}: command completed successfully.")
            if talk:
                say("completed")

        # reboot host
        if reboot_host:
            special_string = "bouncing_ball_9183"
            cmd = f"ssh {host_fqdn} 'echo '{special_string}'; sudo reboot'"
            r = subprocess.run(
                cmd,
                shell=True,
                # will return 255 on success because remote end disconnected...
                check=False,
                stderr=subprocess.STDOUT,
                stdout=subprocess.PIPE,
            )
            # if special string in output, success. else failure.
            process_output = r.stdout.decode()
            if special_string not in process_output:
                print(process_output)
                raise Exception("couldn't reboot host")
            if verbose:
                status_print(f"{hostname}: host rebooted.")
                if talk:
                    say("rebooted")

        # lift quarantine
        # if not dont_lift_quarantine:
        #     if verbose:
        #         status_print(f"{hostname}: lifting quarantine...", end="")
        #     self.q.lift_quarantine(
        #         self.provisioner, self.worker_type, [hostname], verbose=False
        #     )
        #     # TODO: verify?
        #     if verbose:
        #         print(" lifted.")
        #         if talk:
        #             say("quarantine lifted")
        # else:
        #     if verbose:
        #         status_print(f"{hostname}: NOT lifting quarantine (per option).")


# from stack overflow
def remove_argument(a_parser, arg):
    for action in a_parser._actions:
        # print(action)
        opts = action.option_strings
        if (opts and opts[0] == arg) or action.dest == arg:
            a_parser._remove_action(action)
            break

    for action in a_parser._action_groups:
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
        "*** ctrl-c detected. will exit after current host "
        "(one more to exit immediately)."
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
        + """                                            .o88o.
                                            888 `"
oooo  oooo  ooo. .oo.    .oooo.o  .oooo.   o888oo   .ooooo.
`888  `888  `888P"Y88b  d88(  "8 `P  )88b   888    d88' `88b
 888   888   888   888  `"Y88b.   .oP"888   888    888ooo888
 888   888   888   888  o.  )88b d8(  888   888    888    .o
 `V88V"V8P' o888o o888o 8""888P' `Y888""8o o888o   `Y8bod8P'

oooo d8b oooo  oooo  ooo. .oo.   ooo. .oo.    .ooooo.  oooo d8b
`888""8P `888  `888  `888P"Y88b  `888P"Y88b  d88' `88b `888""8P
 888      888   888   888   888   888   888  888ooo888  888
 888      888   888   888   888   888   888  888    .o  888
d888b     `V88V"V8P' o888o o888o o888o o888o `Y8bod8P' d888b
"""  # noqa: W605
        + colorama.Style.RESET_ALL
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=("runs a command against a set of hosts")
    )
    parser.add_argument(
        "--resume_dir",
        "-r",
        metavar="RUN_DIR",
        # custom action that removes the positional args
        action=ResumeAction,
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
    # TODO: add argument to do a reboot if run is successful?
    parser.add_argument(
        "--fqdn-postfix",
        "-F",
        help=(
            "string to append to host (used for ssh check). "
            f"defaults to '{UnsafeRunner.default_fqdn_postfix}'."
        ),
    )
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
        say("unsafe runner: talk enabled", background_mode=True)

    if not args.resume_dir:
        sr = UnsafeRunner(args.hosts, args.command)
    else:
        sr = UnsafeRunner.from_resume(args.resume_dir)

    # get user to ack what we're about to do
    # TODO: mention skipped hosts?
    print("Run options:")
    print(f"  command: {sr.command}")
    # TODO: mention talk, reboot, pre-quarantine count
    print(f"  hosts ({len(sr.remaining_hosts)}): {', '.join(sr.remaining_hosts)}")
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
    #   - this will wait on current host if not drained
    #       (when other hosts in pre-quarantine group are ready)
    host_total = len(sr.remaining_hosts)
    global terminate
    terminate = 0
    # print(list(sr.remaining_hosts))

    remaining_hosts = list(sr.remaining_hosts)
    while remaining_hosts:
        remaining_hosts = list(sr.remaining_hosts)

        exit_while = False
        while True:
            # print("0", end="", flush=True)
            status_print("waiting for ssh-able hosts... ")
            # idle_hosts = sr.si.wait_for_idle_hosts(
            #     pre_quarantine_hosts, show_indicator=True
            # )
            # status_print(
            #     f"idle pre-quarantined hosts found: {', '.join(idle_hosts)}."
            # )

            # # randomize host list
            if not args.do_not_randomize:
                random.shuffle(remaining_hosts)

            for i_host in remaining_hosts:
                # print(".", end="", flush=True)
                i_host_fqdn = f"{i_host}{sr.fqdn_postfix}"
                status_print(f"checking for ssh: {i_host_fqdn}...")
                if host_is_sshable(i_host_fqdn):
                    host = i_host
                    exit_while = True
                    break
            # print("Z", end="", flush=True)
            if exit_while:
                break
            sleep_time = 60
            status_print(f"no ssh-able hosts found. sleeping {sleep_time}s...")
            time.sleep(sleep_time)
        # print(" found.", flush=True)

        # safe_run_single_host
        status_print(f"{host}: starting")
        if args.talk:
            say(f"starting {host}")
        sr.safe_run_single_host(
            host,
            sr.command,
            talk=args.talk,
            # dont_lift_quarantine=args.dont_lift_quarantine,
            reboot_host=args.reboot_host,
        )
        sr.remaining_hosts.remove(host)
        status_print(f"{host}: complete")
        status_print(
            f"hosts remaining ({len(sr.remaining_hosts)}/{host_total}): "
            f"{', '.join(sr.remaining_hosts)}"
        )
        if args.talk:
            # say(f"completed {host}.")
            say(f"{len(sr.remaining_hosts)} hosts remaining.")
        sr.completed_hosts.append(host)
        sr.checkpoint_toml()
        if terminate > 0:
            status_print("graceful exiting...")
            # TODO: show quarantined hosts?
            break
    # TODO: play success sound
    # TODO: can we show any stats?
    status_print("all hosts complete!")
