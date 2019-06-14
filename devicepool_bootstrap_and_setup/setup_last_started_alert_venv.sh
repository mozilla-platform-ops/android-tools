#!/usr/bin/env bash

set -e
# set -x

PATH="/home/bitbar/android-tools/devicepool_last_started_alert"

cd $PATH
# TODO: if it already exists, don't run next bits
if [ ! -d "$PATH/venv" ]; then
  echo "creating venv"
  virtualenv venv
  . venv/bin/activate
  pip install -r requirements.txt
fi
else
  echo "venv already exists"
fi