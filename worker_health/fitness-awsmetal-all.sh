#!/usr/bin/env bash

set -e
# set -x

./fitness_check.py -p gecko-t -hh -s t-linux-metal "$@"
