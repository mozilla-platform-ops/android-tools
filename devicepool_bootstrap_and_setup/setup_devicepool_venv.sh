#!/usr/bin/env bash

set -e
# set -x

cd /home/bitbar/mozilla-bitbar-devicepool
# TODO: if it already exists, don't run next bits
virtualenv venv
. venv/bin/activate
pip install -r requirements.txt