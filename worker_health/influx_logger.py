#!/usr/bin/env python3

import argparse
import os
import logging
import sys
import time

try:
    import schedule
    import toml
    from influxdb import InfluxDBClient
except ImportError:
    print("Missing dependencies. Please run `pipenv install; pipenv shell` and retry!")
    sys.exit(1)

# log_format = '%(asctime)s %(levelname)-10s %(funcName)s: %(message)s'
log_format = "%(levelname)-10s %(funcName)s: %(message)s"
logging.basicConfig(format=log_format, stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger()

import worker_health

class InfluxLogger:

    def __init__(self, log_level, time_limit):
        self.wh = worker_health.WorkerHealth(log_level)
        self.time_limit = time_limit
        self.logging_enabled = False

        # config file
        self.configuration_file = os.path.join(
            os.path.expanduser("~"), ".bitbar_influx_logger.toml"
        )
        self.toml = self.read_toml()

        # influx
        self.influx_host = self.toml["influx"]["host"]
        self.influx_port = self.toml["influx"]["port"]
        self.influx_user = self.toml["influx"]["user"]
        self.influx_pass = self.toml["influx"]["pass"]
        self.influx_db = self.toml["influx"]["db"]

        if (self.influx_host and self.influx_port and
                self.influx_user and self.influx_pass and self.influx_db):
            self.logging_enabled = True
            self.influx_client = InfluxDBClient(
                host=self.influx_host,
                port=self.influx_port,
                username=self.influx_user,
                password=self.influx_pass,
                database=self.influx_db,
                # TODO: should config take these?
                ssl=True,
                verify_ssl=True,
            )

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
host = ""
port = ""
user = ""
pass = ""
db = ""
          """
            return_dict = toml.loads(default_doc)
            self.write_toml(return_dict)
            return return_dict

    # writes lists of strings to influx in line format
    def write_multiline_influx_data(self):
        if self.logging_enabled:
            self.influx_client.write(self.wh.influx_log_lines_to_send,
                 {"db": self.influx_db}, 204, "line")
            logging.info("wrote %s line(s) to influx" % len(self.wh.influx_log_lines_to_send))
        else:
            logging.info("test mode: would have written: '%s'" % self.wh.influx_log_lines_to_send)
        # zero out lines to send
        self.wh.influx_log_lines_to_send = []

    # def do_configured_worker_influx_logging(self):
    #     logger.info("here now")

    # def do_problem_worker_influx_logging(self):
    #     logger.info("here now")

    # logs both problem and configured data
    def do_worker_influx_logging(self):
        logger.info("here now")

        # TODO: DO EEET


        self.wh.influx_report()
        sys.exit(0)

        self.write_multiline_influx_data()

    def main(self, args):
        if self.logging_enabled:
            logger.info("logging enabled!")
        else:
            logger.warning(
                "logging _not_ enabled. please edit '%s' and rerun."
                % self.configuration_file
            )

        if not self.wh.bitbar_systemd_service_present():
            logger.error(
                "this should only be run on the primary mozilla-bitbar-devicepool host"
            )
            sys.exit(1)

        testing_mode_enabled = True
        if not testing_mode_enabled:
            raise('define production mode schedules!')
        else:
            minutes_to_run = 15
            # logger.info("jobs will run every %s minutes" % minutes_to_run)

            # run one right now
            # logger.info("running once immediately")
            self.do_worker_influx_logging()

            # test schedule
            # schedule.every(minutes_to_run).minutes.do(self.do_configured_worker_influx_logging)
            # schedule.every(minutes_to_run).minutes.do(self.do_problem_worker_influx_logging)
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
    args = parser.parse_args()

    sa = InfluxLogger(args.log_level, args.time_limit)
    sa.main(args)
