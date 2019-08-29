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
set +e
ssh relops@"$the_host" id > /dev/null 2>&1
if [ $? -eq 0 ]; then
  echo "performing first bootstrap phase"
  # TODO: add "-o StrictHostKeyChecking=no"?
  scp "$bootstrap_script_path" relops@"$the_host":/tmp/
  # run first as bootstrap user (relops)
  ssh relops@"$the_host" sudo /tmp/bootstrap_bitbar_devicepool.sh || true
else
  echo "host does not have a relops user, skipping first bootstrap phase..."
fi
set -e

# now run as current user and remove relops user (fails in prior run)
echo "performing second bootstrap phase"
# scp "$bootstrap_script_path" "$the_host":/tmp/
# ssh "$the_host" sudo /tmp/bootstrap_bitbar_devicepool.sh
./devicepool_update.sh $the_host

# success message is done in devicepool_update.sh
