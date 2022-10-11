#!/usr/bin/env bash

set -e
set -x

. ./common.sh

# ensure critical scripts/files exist
if [ ! -e "$BOOTSTRAP_SCRIPT_PATH" ]; then
  echo "Couldn't find BOOTSTRAP_SCRIPT_PATH ('$BOOTSTRAP_SCRIPT_PATH')"
  exit 1
fi

if [ ! -e "$BITBAR_ENV_FILE_PATH" ]; then
  echo "Couldn't find BITBAR_ENV_FILE_PATH ('$BITBAR_ENV_FILE_PATH')"
  exit 1
fi
# TODO: check sops repo path

# devicepool-X.relops.mozops.net
export the_host="$1"

if [ -z "$the_host" ]; then
  echo "ERROR: Please provide a host to update (like devicepool-0.relops.mozops.net)"
  exit 1
fi

#
# UPDATE THINGS NOT DONE BY PUPPET
#
echo "updating repos..."
# TODO: get user's ack to update these repos... could stomp on things...
ssh "$the_host" 'sudo -iu bitbar bash -c "cd ~bitbar/android-tools && git pull --rebase"'
ssh "$the_host" 'sudo -iu bitbar bash -c "cd ~bitbar/mozilla-bitbar-devicepool && git pull --rebase"'
# TODO: pipenv install?

#
# RUN PUPPET
#

echo "running puppet..."
scp "$BOOTSTRAP_SCRIPT_PATH" "$the_host":/tmp/
ssh "$the_host" sudo /tmp/bootstrap_bitbar_devicepool.sh

#
# SETUP
#

# TODO: pull out into script called devicepool_credentials.sh?

sops_subdir="secrets/relops"
full_path="${PATH_TO_SOPS_REPO}/${sops_subdir}"
influx_host=$(sops -d "${full_path}/bitbar_influx_logger.toml" | tq - .influx.host)
influx_user=$(sops -d "${full_path}/bitbar_influx_logger.toml" | tq - .influx.user)
influx_pass=$(sops -d "${full_path}/bitbar_influx_logger.toml" | tq - .influx.pass)
# do sed on telegraf config
ssh "$the_host" sudo sed -i.bak "s/INFLUX_HOST/${influx_host}/" /etc/telegraf/telegraf.d/devicepool.conf
ssh "$the_host" sudo sed -i.bak "s/INFLUX_USER/${influx_user}/" /etc/telegraf/telegraf.d/devicepool.conf
ssh "$the_host" sudo sed -i.bak "s/INFLUX_PASS/${influx_pass}/" /etc/telegraf/telegraf.d/devicepool.conf
# restart telegraf
ssh "$the_host" sudo systemctl restart telegraf

# do sed on pagerduty token
pd_token=$(sops -d "${full_path}/bitbar_secrets.toml" | tq - .pagerduty.token)
ssh "$the_host" sudo sed -i.bak "s/replace-this-invalid-token/${pd_token}/" /etc/systemd/system/bitbar-last_started_alert.service
ssh "$the_host" sudo systemctl daemon-reload
# don't restart bitbar-last_started_alert... not sure if this is the active node
# ssh "$the_host" sudo systemctl restart bitbar-last_started_alert

# TODO: place slack_alert and influx_logger configs

# TODO: grab this from SOPS vs local clone of devicepool
./distribute_bitbar_env.sh "$the_host"

# venvs are now created in puppet

cat << 'EOF'

 ___ _   _  ___ ___ ___  ___ ___
/ __| | | |/ __/ __/ _ \/ __/ __|
\__ \ |_| | (_| (_|  __/\__ \__ \
|___/\__,_|\___\___\___||___/___/


EOF
