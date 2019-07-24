#!/usr/bin/env python3

import argparse
import os
import pprint
import sys
import time

from worker_health import WorkerHealth, logger

try:
    from influxdb import InfluxDBClient
    import schedule
    import toml
except ImportError:
    print("Missing dependencies. Please run `pipenv install; pipenv shell` and retry!")
    sys.exit(1)


class InfluxLogger:
    def __init__(self, log_level, time_limit, testing_mode):
        self.wh = WorkerHealth(log_level)
        self.time_limit = time_limit
        self.logging_enabled = False
        self.testing_mode = testing_mode

        # config file
        self.configuration_file = os.path.join(
            os.path.expanduser("~"), ".bitbar_influx_logger.toml"
        )
        self.toml = self.read_toml()

        self.pp = pprint.PrettyPrinter(indent=2)

        # influx
        self.influx_host = self.toml["influx"]["host"]
        self.influx_port = self.toml["influx"]["port"]
        self.influx_user = self.toml["influx"]["user"]
        self.influx_pass = self.toml["influx"]["pass"]
        self.influx_db = self.toml["influx"]["db"]
        self.influx_ssl = self.toml["influx"]["ssl"]
        self.influx_verify_ssl = self.toml["influx"]["verify_ssl"]

        if (
            self.influx_host
            and self.influx_port
            and self.influx_db
        ):
            self.influx_client = InfluxDBClient(
                host=self.influx_host,
                port=self.influx_port,
                username=self.influx_user,
                password=self.influx_pass,
                ssl=self.influx_ssl,
                verify_ssl=self.influx_verify_ssl,
            )
            self.logging_enabled = True

    def write_toml(self, dict_to_write):
        with open(self.configuration_file, "w") as writer:
            toml.dump(dict_to_write, writer)

    def read_toml(self):
        if os.path.exists(self.configuration_file):
            return toml.load(self.configuration_file)
        else:
            # first run
            default_doc = """
[influx]
host = "localhost"
port = 8086
user = ""
pass = ""
db = "testing"
ssl = false
verify_ssl = false
          """
            return_dict = toml.loads(default_doc)
            self.write_toml(return_dict)
            return return_dict

    # writes lists of strings to influx in line format
    def write_multiline_influx_data(self):
        if self.logging_enabled:
            self.influx_client.write(
                self.wh.influx_log_lines_to_send, {"db": self.influx_db}, 204, "line"
            )
            logger.info(
                "wrote %s line(s) to influx" % len(self.wh.influx_log_lines_to_send)
            )
            if self.testing_mode:
                logger.info(
                "lines written: \n%s" % self.pp.pformat(self.wh.influx_log_lines_to_send)
                )
        else:
            logger.info(
                "test mode: would have written: \n%s" % self.pp.pformat(self.wh.influx_log_lines_to_send)
            )
        # zero out lines to send
        self.wh.influx_log_lines_to_send = []

    # logs both problem and configured data
    def do_worker_influx_logging(self):
        logger.info("gathering data and generating influx log lines...")
        self.wh.influx_report(time_limit=self.time_limit)
        logger.info("writing log lines to influx...")
        self.write_multiline_influx_data()

    def main(self):
        if self.logging_enabled:
            logger.info("logging enabled!")
        else:
            logger.warning(
                "logging _not_ enabled. please edit '%s' and rerun."
                % self.configuration_file
            )

        if self.testing_mode:
            self.wh.bitbar_systemd_service_present(warn=True)

            testing_mode_start_delay = 10
            logger.warning(
                "testing mode enabled! logging can still occur if configured."
            )
            if testing_mode_start_delay:
                logger.warning("starting in %s seconds..." % testing_mode_start_delay)
                time.sleep(testing_mode_start_delay)

        else:
            if not self.wh.bitbar_systemd_service_present(error=True):
                # check call messages
                sys.exit(1)

        if not self.testing_mode:
            raise ("define production mode schedules!")
        else:
            minutes_to_run = 5
            logger.info("jobs will run every %s minutes" % minutes_to_run)

            # run one right now
            logger.info("running once immediately")
            self.do_worker_influx_logging()

            # test schedule
            schedule.every(minutes_to_run).minutes.do(self.do_worker_influx_logging)

        while True:
            schedule.run_pending()
            time.sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
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
    parser.add_argument(
        "--testing-mode", action="store_true", default=False, help="enable testing mode"
    )
    args = parser.parse_args()

    # TODO: just pass args?
    sa = InfluxLogger(args.log_level, args.time_limit, args.testing_mode)
    sa.main()
