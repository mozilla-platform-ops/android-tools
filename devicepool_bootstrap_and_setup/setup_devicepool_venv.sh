#!/usr/bin/env bash

set -e
# set -x

cd /home/bitbar/mozilla-bitbar-devicepool
virtualenv venv
. venv/bin/activate
pip install -r requirements.txt