#!/usr/bin/env bash

set -e
# set -x

bootstrap_script_path="$HOME/git/ronin_puppet/provisioners/linux/bootstrap_bitbar_devicepool.sh"
bitbar_env_file_path="$HOME/git/mozilla-bitbar-devicepool/bitbar_env.sh"

# ensure critical scripts/files exist
if [ ! -e "$bootstrap_script_path" ]; then
  echo "Couldn't find bootstrap_script_path ('$bootstrap_script_path')"
  exit 1
fi

if [ ! -e "$bitbar_env_file_path" ]; then
  echo "Couldn't find bitbar_env_file_path ('$bitbar_env_file_path')"
  exit 1
fi

# devicepool-X.relops.mozops.net
export the_host="$1"

if [ -z "$the_host" ]; then
  echo "ERROR: Please provide a host to bootstrap (like devicepool-0.relops.mozops.net)"
  exit 1
fi


#
# BOOTSTRAP
#

# TODO: detect which phase we're in, don't rerun first phase if we don't need to

# TODO: add "-o StrictHostKeyChecking=no"?
scp "$bootstrap_script_path" relops@"$the_host":.
# run first as bootstrap user (relops)
ssh relops@"$the_host" sudo ./bootstrap_bitbar_devicepool.sh || true
# now run as current user and remove relops user (fails in prior run)
ssh "$the_host" sudo ~relops/bootstrap_bitbar_devicepool.sh


#
# SETUP
#

scp "$bitbar_env_file_path" "$the_host":bitbar.env
ssh "$the_host" 'sudo mv bitbar.env /etc/bitbar/ && sudo chown root:bitbar /etc/bitbar/bitbar.env && sudo chmod 660 /etc/bitbar/bitbar.env'

# create venv and pip install -r requirements.txt
devicepool_venv_setup_script_name="setup_devicepool_venv.sh"
devicepool_venv_setup_script_remote_path="/tmp/${devicepool_venv_setup_script_name}"
scp "./$devicepool_venv_setup_script_name" "$the_host":"$devicepool_venv_setup_script_remote_path"
ssh "$the_host" "chmod 755 $devicepool_venv_setup_script_remote_path"
ssh "$the_host" "sudo -iu bitbar '$devicepool_venv_setup_script_remote_path'"

cat << 'EOF'

 ___ _   _  ___ ___ ___  ___ ___
/ __| | | |/ __/ __/ _ \/ __/ __|
\__ \ |_| | (_| (_|  __/\__ \__ \
|___/\__,_|\___\___\___||___/___/
                                 

EOF
