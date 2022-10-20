#!/usr/bin/env bash

set -e
# set -x

./fitness_check.py \
 --ping \
 --ping-domain test.releng.mdc2.mozilla.com \
  -p releng-hardware \
  gecko-t-linux-talos "$@"
