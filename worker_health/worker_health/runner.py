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

import alive_progress
import colorama
import taskcluster
import tomlkit

from worker_health import quarantine, status, utils

# user todos
# TODO: remove need for fqdn-postfix arg
#   - where to get this data from?
# TODO: command to dump an empty state file in restore dir

# developer todos
# TODO: move these non-class functions to utils?


def natural_sort_key(s, _nsre=re.compile("([0-9]+)")):
    return [int(text) if text.isdigit() else text.lower() for text in _nsre.split(s)]


def get_fully_qualified_hostname(host, postfix):
    return f"{host}.{postfix}"


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
            raise Exception("Invalid value %s, values must be a number (%s)" % (vstr, err))
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


class CommandFailedException(Exception):
    pass


class Runner:
    default_pre_quarantine_additional_host_count = 5
    default_fqdn_postfix = "test.releng.mdc1.mozilla.com"
    state_file_name = "runner_state.toml"
    # TODO: use tomlkit tables so formatting is nice for empty lists?
    empty_config_dict = {
        "config": {
            "command": "ssh SR_HOST.SR_FQDN",
            "hosts_to_skip": [],
            "fqdn_prefix": "",
        },
        "state": {
            "remaining_hosts": [],
            "failed_hosts": [],
            "completed_hosts": [],
        },
    }

    def __init__(
        self,
        hosts=[],
        command="ssh SR_HOST.SR_FQDN",
        fqdn_prefix=default_fqdn_postfix,
        safe_mode=False,
        provisioner=None,
        worker_type=None,
    ):
        # required args
        self.command = command
        self.fqdn_postfix = fqdn_prefix
        # optional args
        self.provisioner = provisioner
        self.worker_type = worker_type

        # TODO: should we store this? so write will preserve comments?
        # self._config_toml = {}
        # state
        self.completed_hosts = []
        self.failed_hosts = []
        self.remaining_hosts = hosts

        # TODO: init to something else?
        self.hosts_to_skip = []

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
        resume_file = f"{resume_dir}/{Runner.state_file_name}"

        if not os.path.exists(resume_file):
            # write emtpy file
            # TODO: verify user wants this
            print("no state file found in directory, creating empty file and exiting...")
            with open(resume_file, "w") as f:
                tomlkit.dump(cls.empty_config_dict, f)
            sys.exit(0)

        # load file
        with open(resume_file, "rb") as f:
            try:
                data = tomlkit.load(f)
            except tomlkit.exceptions.UnexpectedCharError as e:
                print(f"FATAL: invalid format in state file ({resume_file})")
                print(f"  {e}")
                sys.exit(1)

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
        try:
            i = cls(
                provisioner=data["config"]["provisioner"],
                worker_type=data["config"]["worker_type"],
                hosts=data["state"]["remaining_hosts"],
                command=data["config"]["command"],
                fqdn_prefix=data["config"]["fqdn_prefix"],
            )
        except tomlkit.exceptions.NonExistentKey as e:
            print(f"Missing required config file param: {str(e)}")
            sys.exit(1)
        # populate rest
        i.completed_hosts = data["state"]["completed_hosts"]
        i.failed_hosts = data["state"]["failed_hosts"]
        i.hosts_to_skip = data["config"]["hosts_to_skip"]
        i.run_dir = resume_dir
        i.state_file = f"{resume_dir}/{Runner.state_file_name}"
        return i

    @property
    def default_rundir_path(self):
        datetime_format_for_directory = "%Y%m%d-%H%M%S"
        datetime_part = self.start_datetime.strftime(datetime_format_for_directory)
        return f"runner_run_{datetime_part}"

    @property
    def default_state_file_path(self):
        return f"{self.default_rundir_path}/{Runner.state_file_name}"

    def write_initial_toml(self):
        # populate data
        data = copy.deepcopy(Runner.empty_config_dict)
        # config
        data["config"]["provisioner"] = self.provisioner
        data["config"]["worker_type"] = self.worker_type
        data["config"]["command"] = self.command
        data["config"]["fqdn_prefix"] = self.fqdn_postfix
        data["config"]["hosts_to_skip"] = self.hosts_to_skip
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
        data["state"]["failed_hosts"] = self.failed_hosts
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
        quarantine_mode=False,
        dont_lift_quarantine=False,
        continue_on_failure=False,
    ):
        host_fqdn = get_fully_qualified_hostname(hostname, self.fqdn_postfix)
        # TODO: ensure command has SR_HOST variable in it
        if "SR_HOST" not in command and "SR_FQDN" not in command:
            raise Exception("command doesn't have SR_HOST or SR_FQDN in it!")

        # quarantine
        # TODO: check if already quarantined and skip if so
        if quarantine_mode:
            if verbose:
                status_print(f"{hostname}: adding to quarantine...")
            try:
                self.q.quarantine(self.provisioner, self.worker_type, [hostname], verbose=False)
                # TODO: verify?
                if verbose:
                    status_print(f"{hostname}: quarantined.")
                    if talk:
                        say("quarantined")
            except taskcluster.exceptions.TaskclusterRestFailure:
                status_print(f"INFO: safe_run_single_host: no TC record of {hostname}, skipping quarantine...")

        # TODO: check that nc is present first
        # if we waited, the host just finished a job and is probably rebooting, so
        # wait for host to be back up, otherwise ssh will time out.

        if verbose:
            status_print(f"{hostname}: waiting for ssh to be up... ")
        #     if talk:
        #         say("waiting for ssh")
        while True:
            if host_is_sshable(host_fqdn):
                break
            time.sleep(5)
        if verbose:
            status_print(f"{hostname}: ssh is up.")

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

        # do substitutions
        custom_cmd_temp = command.replace("SR_HOST", hostname)
        custom_cmd = custom_cmd_temp.replace("SR_FQDN", self.fqdn_postfix)
        # run command
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
            if continue_on_failure:
                raise CommandFailedException("command failed")
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
        if quarantine_mode and not dont_lift_quarantine:
            if verbose:
                status_print(f"{hostname}: lifting quarantine...")
            try:
                self.q.lift_quarantine(self.provisioner, self.worker_type, [hostname], verbose=False)
            except taskcluster.exceptions.TaskclusterRestFailure:
                status_print(f"no TC record of {hostname}, can't lift quarantine.")
                return
            # TODO: verify?
            if verbose:
                status_print(f"{hostname}: quarantine lifted.")
                if talk:
                    say("quarantine lifted")
        else:
            if verbose:
                status_print(f"{hostname}: NOT lifting quarantine (per option).")


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
        remove_argument(parser, "fqdn_prefix")
        # the normal part
        setattr(args, self.dest, values)


def handler(_signum, _frame):
    global terminate
    terminate += 1
    print("")
    if terminate >= 2:
        print("*** double ctrl-c detected. exiting immediately!")
        sys.exit(0)
    print("*** ctrl-c detected. will exit after current host " "(one more to exit immediately).")


# given a string hostname, returns True if sshable, else False.
def host_is_sshable(hostname):
    up_check_cmd = f"nc -w 2 -G 3 -z {hostname} 22 2>&1"
    spr = subprocess.run(up_check_cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, shell=True)
    rc = spr.returncode
    if rc == 0:
        return True
    return False


def ur_print_banner():
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
        + colorama.Style.RESET_ALL,
    )


def sr_print_banner():
    # from `figlet -f smslant safe runner`
    # looks strange as first line is indented
    print(
        colorama.Style.BRIGHT
        + """            ___
  ___ ___ _/ _/__   ______ _____  ___  ___ ____
 (_-</ _ `/ _/ -_) / __/ // / _ \/ _ \/ -_) __/
/___/\_,_/_/ \__/ /_/  \_,_/_//_/_//_/\__/_/
"""  # noqa: W605
        + colorama.Style.RESET_ALL,
    )


# TODO: should exit immediately when waiting, requires two frequently
#    - need more checks for exit state (vs just at end)
# TODO: rework how alive progress bars work... off at times
def main(args, safe_mode=False):
    if safe_mode:
        name_string = "safe runner"
        sr_print_banner()
    else:
        name_string = "unsafe runner"
        ur_print_banner()

    if args.talk:
        say(f"{name_string}: talk enabled", background_mode=True)

    if not args.resume_dir:
        sr = Runner(hosts=args.hosts, command=args.command, fqdn_prefix=args.fqdn_prefix)
        print(f"state file (new): {sr.state_file}")
    else:
        sr = Runner.from_resume(args.resume_dir)
        print(f"state file (resumed): {sr.state_file}")

    # TODO: config check
    #   - catch missing data before try/catch below

    # get user to ack what we're about to do
    # TODO: mention skipped hosts?
    try:
        print("run options:")
        print(f"  hosts ({len(sr.remaining_hosts)}): {', '.join(sr.remaining_hosts)}")
        print(f"    fqdn_postfix: {sr.fqdn_postfix}")
        # TODO: mention talk, reboot, pre-quarantine count
        if safe_mode:
            print(f"    TC provisioner: {sr.provisioner}")
            print(f"    TC workerType: {sr.worker_type}")
        print(f"  command: {sr.command}")
        print("")
    except AttributeError as e:
        print("FATAL: missing config value!?!")
        print(f"  {e}")
        sys.exit(1)
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

    # TODO: stop doing this, just cast to list where needed?
    #   - can't because we need to persist the non-list
    remaining_hosts = list(sr.remaining_hosts)
    completed_hosts = list(sr.completed_hosts)
    failed_hosts = list(sr.failed_hosts)
    skipped_hosts = list(sr.hosts_to_skip)
    total_hosts = len(
        # TODO: need to add failed for correct counts
        set(remaining_hosts)
        .union(set(completed_hosts))
        .union(set(skipped_hosts))
        .union(set(failed_hosts)),
    )

    # TODO: should bar length be total hosts or remaining hosts?
    with alive_progress.alive_bar(total=total_hosts, enrich_print=False, stats=False) as bar:
        # init bar count
        bar(len(completed_hosts) + len(failed_hosts))

        while remaining_hosts:
            remaining_hosts = list(sr.remaining_hosts)
            completed_hosts = list(sr.completed_hosts)
            failed_hosts = list(sr.failed_hosts)

            exit_while = False
            # bar.pause()
            while True:
                # print("0", end="", flush=True)
                if safe_mode:
                    status_print("TODO: pre-quarantine not supported yet")

                    # print(sr.remaining_hosts)
                    tl = list(sr.remaining_hosts)
                    pre_quarantine_hosts = tl[0 : (args.pre_quarantine_additional_host_count + 1)]
                    idle_hosts = sr.si.wait_for_idle_hosts(pre_quarantine_hosts, show_indicator=False)
                    status_print(f"idle pre-quarantined hosts found: {', '.join(idle_hosts)}.")

                    remaining_hosts = idle_hosts
                    status_print("TODO: support safe mode: wait for idle hosts (vs remaining)")

                # randomize host list
                if not args.do_not_randomize:
                    random.shuffle(remaining_hosts)

                status_print("waiting for ssh-able hosts... ")
                for i_host in remaining_hosts:
                    # print(".", end="", flush=True)
                    i_host_fqdn = get_fully_qualified_hostname(i_host, sr.fqdn_postfix)
                    status_print(f"checking for ssh: {i_host_fqdn}...")
                    if host_is_sshable(i_host_fqdn):
                        host = i_host
                        exit_while = True
                        break
                if exit_while:
                    break
                # print("Z", end="", flush=True)
                sleep_time = 60
                status_print(f"no ssh-able hosts found. sleeping {sleep_time}s...")
                time.sleep(sleep_time)
            # print(" found.", flush=True)
            # bar.unpause()

            status_print(f"starting {host}...")
            if args.talk:
                say(f"starting {host}")
            try:
                sr.safe_run_single_host(
                    host,
                    sr.command,
                    talk=args.talk,
                    reboot_host=args.reboot_host,
                    quarantine_mode=safe_mode,
                    dont_lift_quarantine=args.dont_lift_quarantine,
                    continue_on_failure=True,
                )
            except CommandFailedException:
                # TODO: control decision to continue or exit via flag
                print("command failed, continuing...")
                sr.remaining_hosts.remove(host)
                remaining_hosts = list(sr.remaining_hosts)
                sr.failed_hosts.append(host)
                bar()
                sr.checkpoint_toml()
                if terminate > 0:
                    status_print("graceful exiting...")
                    # TODO: show quarantined hosts?
                    sys.exit(0)
                    break
                continue
            sr.remaining_hosts.remove(host)
            # update this so this exits
            # TODO: remove need for remaining_hosts... feels gross
            remaining_hosts = list(sr.remaining_hosts)
            status_print(f"completed {host}")
            status_print(
                f"hosts remaining ({len(sr.remaining_hosts)}/{host_total}): " f"{', '.join(sr.remaining_hosts)}",
            )
            if args.talk:
                # say(f"completed {host}.")
                say(f"{len(sr.remaining_hosts)} hosts remaining.")
            sr.completed_hosts.append(host)
            bar()
            sr.checkpoint_toml()
            if terminate > 0:
                status_print("graceful exiting...")
                sys.exit(0)
                # TODO: show quarantined hosts?
                break
        # TODO: play success sound
        # TODO: can we show any stats?
        status_print("all hosts complete!")
