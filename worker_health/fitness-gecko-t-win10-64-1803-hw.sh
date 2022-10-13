#!/usr/bin/env bash

set -e
# set -x

./fitness_check.py \
  -p releng-hardware \
  gecko-t-win10-64-1803-hw "$@"
