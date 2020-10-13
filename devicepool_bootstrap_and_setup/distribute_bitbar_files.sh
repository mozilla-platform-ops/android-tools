#!/usr/bin/env bash

set -e

. ./common.sh

the_host=$1

if [ -z "$the_host" ]; then
  echo "A destination host must be specified."
  exit 1
fi

tempdir="/tmp/disribute_bitbar_files"
destdir="/home/bitbar/mozilla-bitbar-devicepool/files"

set -x

# show what's there now
ssh "$the_host" ls -l ${destdir} || true

# shellcheck disable=SC2029  # we want tempdir expanded
ssh "$the_host" "rm -rf ${tempdir} && mkdir -p ${tempdir}"
# shellcheck disable=SC2086  # we want globbing of tempdir here
# shellcheck disable=SC2154  # bitbar_files_path is exported in common
scp ${bitbar_files_path} "${the_host}":${tempdir}
# shellcheck disable=SC2029  # we want tempdir and destdir expanded
ssh "$the_host" "sudo mv ${tempdir}/* ${destdir} && sudo chown bitbar:bitbar ${destdir}/* && sudo chmod 644 ${destdir}/*"

# show what's there now
ssh "$the_host" ls -l ${destdir}

echo "SUCCESS"
