#!/usr/bin/env bash

set -e

export bootstrap_script_path="$HOME/git/ronin_puppet/provisioners/linux/bootstrap_bitbar_devicepool.sh"
export bitbar_env_file_path="$HOME/git/mozilla-bitbar-devicepool/bitbar_env.sh"
export bitbar_files_path="$HOME/git/mozilla-bitbar-devicepool/files/relops*"
export path_to_sops_repo="$HOME/git/sops"
