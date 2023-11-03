#!/usr/bin/env bash

set -e
# set -x

#  --ping \
#  --ping-domain test.releng.mdc1.mozilla.com \
  #-hh \

./fitness_check.py \
  -p gecko-t \
  -t 75 \
  -o \
  -s \
  t-linux-vm-2204-wayland "$@"
