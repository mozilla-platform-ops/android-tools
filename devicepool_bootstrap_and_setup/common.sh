#!/usr/bin/env bash

set -e

# local paths
export BOOTSTRAP_SCRIPT_PATH="$HOME/git/ronin_puppet/provisioners/linux/bootstrap_bitbar_devicepool.sh"
export BITBAR_ENV_FILE_PATH="$HOME/git/mozilla-bitbar-devicepool/bitbar_env.sh"
export BITBAR_FILES_PATH="$HOME/git/mozilla-bitbar-devicepool/files/relops*"
export PATH_TO_SOPS_REPO="$HOME/git/sops"

# things to diff
export TELEGRAF_CONFIG_FILE='/etc/telegraf/telegraf.d/devicepool.conf'
export LAST_STARTED_SERVICE_FILE='/etc/systemd/system/bitbar-last_started_alert.service'
export SLACK_ALERT_CONFIG_FILE='/home/bitbar/.bitbar_slack_alert.toml'
export INFLUX_LOGGER_CONFIG_FILE='/home/bitbar/.bitbar_influx_logger.toml'
export BITBAR_ENV_FILE='/etc/bitbar/bitbar.env'
