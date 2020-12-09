#!/usr/bin/env bash

set -e
# set -x

BOOTSTRAP_SCRIPT_PATH="$HOME/git/ronin_puppet/provisioners/linux/bootstrap_bitbar_devicepool.sh"
BITBAR_ENV_FILE_PATH="$HOME/git/mozilla-bitbar-devicepool/bitbar_env.sh"

# ensure critical scripts/files exist
if [ ! -e "$BOOTSTRAP_SCRIPT_PATH" ]; then
  echo "Couldn't find BOOTSTRAP_SCRIPT_PATH ('$BOOTSTRAP_SCRIPT_PATH')"
  exit 1
fi

if [ ! -e "$BITBAR_ENV_FILE_PATH" ]; then
  echo "Couldn't find BITBAR_ENV_FILE_PATH ('$BITBAR_ENV_FILE_PATH')"
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
if ! ssh relops@"$the_host" id > /dev/null 2>&1; then
  echo "performing first bootstrap phase"
  # TODO: add "-o StrictHostKeyChecking=no"?
  scp "$BOOTSTRAP_SCRIPT_PATH" relops@"$the_host":/tmp/
  # run first as bootstrap user (relops)
  ssh relops@"$the_host" sudo /tmp/bootstrap_bitbar_devicepool.sh || true
else
  echo "host does not have a relops user, skipping first bootstrap phase..."
fi
set -e

# now run as current user and remove relops user (fails in prior run)
echo "performing second bootstrap phase"
# scp "$BOOTSTRAP_SCRIPT_PATH" "$the_host":/tmp/
# ssh "$the_host" sudo /tmp/bootstrap_bitbar_devicepool.sh
./devicepool_update.sh "$the_host"

# success message is done in devicepool_update.sh
