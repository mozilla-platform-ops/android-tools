#!/usr/bin/env bash

set -e
# set -x

./fitness.py \
 --ping \
 --ping-domain test.releng.mdc2.mozilla.com \
  -p releng-hardware \
  gecko-t-linux-talos "$@"
