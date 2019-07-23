#!/usr/bin/env python3

import argparse
import os
import logging
import sys

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

    def log_configured_workers(self):
        pass

    def log_problem_workers(self):
        pass

    def __init__(self, log_level, time_limit):
        self.wh = worker_health.WorkerHealth(log_level)
        # self.time_limit = time_limit
        self.logging_enabled = False
        # self.bitbar_tz = "America/Los_Angeles"

        # config file
        self.configuration_file = os.path.join(
            os.path.expanduser("~"), ".bitbar_influx_logger.toml"
        )
        self.toml = self.read_toml()

        # webhook url
        # self.webhook_url = self.toml["main"]["webhook_url"]
        # if self.webhook_url:
        #     self.alerting_enabled = True

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
          """
            return_dict = toml.loads(default_doc)
            self.write_toml(return_dict)
            return return_dict

    # only fires if it's 8AM-6PM M-F in bitbar TZ
    # def slack_alert_m_thru_f(self):
    #     now = pendulum.now(tz=self.bitbar_tz)
    #     if (8 <= now.hour <= 18) and (1 <= now.day_of_week < 5):
    #         logger.info("inside run window")
    #         pw = self.wh.get_problem_workers(self.time_limit)
    #         if pw:
    #             message = "problem workers: %s" % pw
    #             self.send_slack_message(message)
    #         else:
    #             logger.info("no problem workers")
    #     else:
    #         logger.info("outside run window")

    # def send_slack_message(self, message):
    #     # cli example:
    #     #   curl -X POST -H 'Content-type: application/json' --data '{"text":"Hello, World!"}' WEBHOOK_URL
    #     data = {"text": message}
    #     r = requests.post(url=self.webhook_url, json=data)
    #     if r.status_code == 200:
    #         logger.info("slack message sent. message: '%s'" % message)
    #     else:
    #         logger.error("failure when trying to send slack message")
    #         logger.error(r.text)
    #         logger.error(r.status_code)

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
            # # run once every hour at specific minute
            # minute_of_hour_to_run = 7
            # minute_at_string = ":%s" % str(minute_of_hour_to_run).zfill(2)
            # logger.info("job will run every hour at %s" % minute_at_string)
            # schedule.every().hour.at(minute_at_string).do(self.slack_alert_m_thru_f)
            pass
        else:
            # minutes_to_run = 10
            # logger.info("job will run every %s minutes" % minutes_to_run)
            # run one right now
            # logger.info("running once immediately")
            # self.slack_alert_m_thru_f()
            # test schedule
            schedule.every(minutes_to_run).minutes.do(self.)
            pass

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
