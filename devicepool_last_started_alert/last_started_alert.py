#!/usr/bin/env python3

import argparse
import datetime
import json
import logging
import os
import pprint
import re
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

import toml
from pdpyras import EventsAPISession

# configuration option-esque constants
MINUTES_OF_LOGS_TO_INSPECT = 30
MINIMUM_LINES_OF_JOURNALCTL_OUTPUT = 10
DAEMON_MODE_CHECK_FREQUENCY_SECONDS = 5 * 60
PD_SERVICE_ID = "PAYN6NV"

# constants
DEDUP_KEY_FORMAT = "lsa_%Y%m%d%H%M"
STATE_FILE = os.path.join(os.path.expanduser("~"), ".last_started_alert_state.toml")
INCIDENT_KEY = "Devicepool Last Started Alert: "
STARTED_REGEX = r"test run [\d]+ started"
FINISHED_REGEX = r"test run [\d]+ finished"
URLS = [
    #    "https://queue.taskcluster.net/v1/pending/proj-autophone/gecko-t-ap-unit-p2",
    #    "https://queue.taskcluster.net/v1/pending/proj-autophone/gecko-t-ap-perf-p2",
    #    "https://queue.taskcluster.net/v1/pending/proj-autophone/gecko-t-ap-batt-p2",
    #    "https://queue.taskcluster.net/v1/pending/proj-autophone/gecko-t-ap-unit-g5",
    #    "https://queue.taskcluster.net/v1/pending/proj-autophone/gecko-t-ap-perf-g5",
    #    "https://queue.taskcluster.net/v1/pending/proj-autophone/gecko-t-ap-batt-g5",
    #    "https://queue.taskcluster.net/v1/pending/proj-autophone/gecko-t-ap-test-g5",
    "https://queue.taskcluster.net/v1/pending/proj-autophone/gecko-t-bitbar-gw-batt-p2",
    "https://queue.taskcluster.net/v1/pending/proj-autophone/gecko-t-bitbar-gw-perf-p2",
    "https://queue.taskcluster.net/v1/pending/proj-autophone/gecko-t-bitbar-gw-unit-p2",
    "https://queue.taskcluster.net/v1/pending/proj-autophone/gecko-t-bitbar-gw-batt-g5",
    "https://queue.taskcluster.net/v1/pending/proj-autophone/gecko-t-bitbar-gw-perf-g5",
    "https://queue.taskcluster.net/v1/pending/proj-autophone/gecko-t-bitbar-gw-unit-g5",
    "https://queue.taskcluster.net/v1/pending/proj-autophone/gecko-t-bitbar-gw-test-g5",
]


class LastStarted:
    def __init__(self):
        self.alerting_enabled = False
        self.pp = pprint.PrettyPrinter(indent=4)
        self.pd_session = None
        self.journalctl_lines_of_output = None

        # TODO: load state from dict
        self.state_dict = self.read_toml()

        # TODO: use the REST API with a full user token to do queries on active incidents
        # - for now will use a dedupe key stored on local disk to detect if incident is already
        #   in progress

        # check that it's present
        if "PAGERDUTY_TOKEN" in os.environ:
            # check that it's non-empty
            if os.environ["PAGERDUTY_TOKEN"]:
                api_token = os.environ["PAGERDUTY_TOKEN"]
                # TODO: rename to pd_event_session
                self.pd_session = EventsAPISession(api_token)
                # TODO: fire an api request and see that it works before setting alerting_enabled
                self.alerting_enabled = True
                self.debug(self.pd_session)

    def debug(self, sess):
        """
        Enables debug level logging to stderr in order to see logging
        """
        sh = logging.StreamHandler()
        sh.setLevel(logging.DEBUG)
        sess.log.addHandler(sh)
        sess.log.setLevel(logging.DEBUG)

    def get_url(self, url):
        data = urlopen(url).read()
        output = json.loads(data)
        return output

    def jobs_in_queues(self):
        count = 0
        for url in URLS:
            json_result = self.get_url(url)
            # print(json_result)
            count += json_result["pendingTasks"]
        return count

    # returns boolean, True if there is already an alert created by this program
    # def open_incidents_already(self):
    #     # https://api.pagerduty.com/incidents?statuses%5B%5D=triggered&statuses%5B%5D=acknowledged&service_ids%5B%5D=PS9CADW&time_zone=UTC
    #     # self.pd_session.rget('/incidents', params={statuses})

    #     incidents = self.pd_api_session.list_all(
    #         'incidents',
    #         params={'service_ids[]':[PD_SERVICE_ID],'statuses[]':['triggered', 'acknowledged']}
    #     )

    #     self.pp.pprint(incidents)

    # searches for any incidents created by this program and closes
    # def resolve_incidents(self):
    #     pass

    def set_currently_alerting(self, currently_alerting=True):
        if currently_alerting == False:
            self.set_dedup_key("")
        self.state_dict["alert_state"]["currently_alerting"] = currently_alerting
        self.write_toml(self.state_dict)

    def set_dedup_key(self, key):
        self.state_dict["alert_state"]["current_dedup_key"] = key
        self.write_toml(self.state_dict)

    # TODO: get rid of need for get_new_if_not_set arg
    #       - add a new function - get_or_create_dedup_key(). cleaner?
    def get_dedup_key(self, get_new_if_not_set=True):
        try:
            dk = self.state_dict["alert_state"]["current_dedup_key"]
        except KeyError:
            # should we ever be here?
            raise Exception("shouldn't ever be here with default toml")
        # handle empty string
        if not dk:
            if get_new_if_not_set:
                dk = self.create_dedup_key()
            else:
                raise Exception("not in incident, why are we calling resolve?")
        return dk

    def currently_alerting(self):
        try:
            return self.state_dict["alert_state"]["currently_alerting"]
        except KeyError:
            return False

    def create_dedup_key(self):
        # date_string=`date +%Y%m%d%H%M`
        now = datetime.datetime.now()
        return now.strftime(DEDUP_KEY_FORMAT)

    # opens a new incident
    def trigger_event(self):
        # docs:
        #   https://v2.developer.pagerduty.com/docs/send-an-event-events-api-v2
        #   https://pagerduty.github.io/pdpyras/#pdpyras.EventsAPISession.trigger

        summary = (
            "Jobs are present in queues, but no 'started' lines in devicepools logs for %s minutes!"
            % MINUTES_OF_LOGS_TO_INSPECT
        )
        hostname = socket.gethostname()
        dedup_key = self.get_dedup_key()

        self.pd_session.trigger(
            summary, hostname, dedup_key=dedup_key, severity="critical"
        )
        self.set_dedup_key(dedup_key)
        self.set_currently_alerting()

        # fields to set:
        # summary:
        # severity: low
        # source: socket.gethostname()

        # optional: component, group, class
        # - see https://v2.developer.pagerduty.com/docs/events-api-v2

        pass

    def resolve_incident(self):
        self.pd_session.resolve(self.get_dedup_key(get_new_if_not_set=False))
        self.set_currently_alerting(False)

    def started_lines_present(self):
        output = self.get_journalctl_output()
        if re.search(STARTED_REGEX, output):
            return True
        return False

    def completed_lines_present(self):
        output = self.get_journalctl_output()
        if re.search(FINISHED_REGEX, output):
            return True
        return False

    def get_journalctl_output(self):
        # NOTE: user running needs to be in adm group to not need sudo
        cmd = (
            "journalctl -u bitbar --since '%s minutes ago'" % MINUTES_OF_LOGS_TO_INSPECT
        )
        res = self.run_cmd(cmd)

        # TODO: ensure that the process has been running for x minutes before being able to trigger alert?
        # - X lines minimum?

        lines = res.split("\n")
        self.journalctl_lines_of_output = len(lines)

        return res

    def run_cmd(self, cmd):
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        proc.wait()
        rc = proc.returncode
        if rc == 0:
            tmp = proc.stdout.read().strip()
            return tmp.decode()
        else:
            raise Exception("non-zero code returned")

    def write_toml(self, dict_to_write):
        with open(STATE_FILE, "w") as writer:
            toml.dump(dict_to_write, writer)

    def enough_journalctl_lines(self):
        if self.journalctl_lines_of_output:
            if self.journalctl_lines_of_output >= MINIMUM_LINES_OF_JOURNALCTL_OUTPUT:
                return True
            return False
        else:
            raise Exception("self.journalctl_lines_of_output not defined!")

    def read_toml(self):
        if os.path.exists(STATE_FILE):
            return toml.load(STATE_FILE)
        else:
            # first run
            default_doc = """
[alert_state]
currently_alerting = false
current_dedup_key = ""
            """
            return_dict = toml.loads(default_doc)
            self.write_toml(return_dict)
            return return_dict

    def perform_check(self, args):
        currently_alerting = self.currently_alerting()
        jobs_in_queues = self.jobs_in_queues()
        started_lines_present = self.started_lines_present()
        completed_lines_present = self.completed_lines_present()
        enough_journalctl_lines = self.enough_journalctl_lines()

        # INFO
        if args.verbose:

            print("Currently alerting?: %s" % currently_alerting)
            print("Jobs in queues: %s" % jobs_in_queues)
            print("Minutes of logs inspected: %s" % MINUTES_OF_LOGS_TO_INSPECT)
            print("Lines of journalctl output: %s" % self.journalctl_lines_of_output)
            print("Enough lines of journalctl output?: %s" % enough_journalctl_lines)
            print("Started lines present?: %s" % started_lines_present)
            print("Completed lines present?: %s" % completed_lines_present)

        # ALERTING
        if self.alerting_enabled:
            # TESTING
            # dk = self.create_dedup_key()
            # self.set_dedup_key(dk)
            # print(self.get_dedup_key())
            # self.set_currently_alerting()
            #
            # self.trigger_event()
            # self.resolve_incident()

            if enough_journalctl_lines:
                if jobs_in_queues:
                    if not started_lines_present:
                        print("*** Alert conditions met! Sending trigger event.")
                        self.trigger_event()
                    else:
                        if currently_alerting:
                            print(
                                "*** Alert conditions not met. Resolving current incident."
                            )
                            self.resolve_incident()
                        else:
                            print("*** Alert conditions not met.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-d", "--daemon-mode", action="store_true")
    args = parser.parse_args()

    ls = LastStarted()
    if ls.alerting_enabled:
        print("Alerting is enabled.")
    else:
        print("Alerting is _not_ enabled.")

    if args.daemon_mode:
        print(
            "Daemon mode activated. Will perform checks every %s seconds."
            % DAEMON_MODE_CHECK_FREQUENCY_SECONDS
        )
        while True:
            ls.perform_check(args)
            time.sleep(DAEMON_MODE_CHECK_FREQUENCY_SECONDS)
    else:
        ls.perform_check(args)
