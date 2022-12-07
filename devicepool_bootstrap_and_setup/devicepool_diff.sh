#!/usr/bin/env bash

set -e

# goal: checksum config files on the devicepool fleet for comparison

# TODO: make this bring configs back to localhost and show diffs

# things to diff
# shellcheck disable=SC2034
TELEGRAF_CONFIG_FILE='/etc/telegraf/telegraf.d/devicepool.conf'
# shellcheck disable=SC2034
LAST_STARTED_SERVICE_FILE='/etc/systemd/system/bitbar-last_started_alert.service'
# shellcheck disable=SC2034
SLACK_ALERT_CONFIG_FILE='/home/bitbar/.bitbar_slack_alert.toml'
# shellcheck disable=SC2034
INFLUX_LOGGER_CONFIG_FILE='/home/bitbar/.bitbar_influx_logger.toml'
# shellcheck disable=SC2034
BITBAR_ENV_FILE='/etc/bitbar/bitbar.env'

CHECKSUM_TO_USE='sha256'
CHECKSUM_COMMAND="openssl $CHECKSUM_TO_USE"

# do it
for file in TELEGRAF_CONFIG_FILE LAST_STARTED_SERVICE_FILE SLACK_ALERT_CONFIG_FILE INFLUX_LOGGER_CONFIG_FILE BITBAR_ENV_FILE; do
    echo "${!file}: "
    for host_number in 0 1 2; do
        hostname="devicepool-${host_number}.relops.mozops.net"
        # echo "checking ${hostname}..."
        ssh "${hostname} sudo ${CHECKSUM_COMMAND} ${!file}"
    done
done
