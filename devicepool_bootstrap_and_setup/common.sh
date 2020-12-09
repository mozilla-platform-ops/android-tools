#!/usr/bin/env bash

set -e

export BOOTSTRAP_SCRIPT_PATH="$HOME/git/ronin_puppet/provisioners/linux/bootstrap_bitbar_devicepool.sh"
export BITBAR_ENV_FILE_PATH="$HOME/git/mozilla-bitbar-devicepool/bitbar_env.sh"
export BITBAR_FILES_PATH="$HOME/git/mozilla-bitbar-devicepool/files/relops*"
export PATH_TO_SOPS_REPO="$HOME/git/sops"
