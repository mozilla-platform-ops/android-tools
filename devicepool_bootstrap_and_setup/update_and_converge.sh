#!/usr/bin/env bash

set -e
set -x

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
  echo "ERROR: Please provide a host to update (like devicepool-0.relops.mozops.net)"
  exit 1
fi

#
# UPDATE THINGS NOT DONE BY PUPPET
#
echo "updating things..."
ssh "$the_host" 'sudo -iu bitbar bash -c "cd ~bitbar/android-tools && git pull --rebase"'
ssh "$the_host" 'sudo -iu bitbar bash -c "cd ~bitbar/mozilla-bitbar-devicepool && git pull --rebase"'
# TODO: pipenv install?

#
# RUN PUPPET
#

# now run as current user and remove relops user (fails in prior run)
echo "running puppet..."
scp "$bootstrap_script_path" "$the_host":/tmp/
ssh "$the_host" sudo /tmp/bootstrap_bitbar_devicepool.sh


cat << 'EOF'

 ___ _   _  ___ ___ ___  ___ ___
/ __| | | |/ __/ __/ _ \/ __/ __|
\__ \ |_| | (_| (_|  __/\__ \__ \
|___/\__,_|\___\___\___||___/___/
                                 

EOF
