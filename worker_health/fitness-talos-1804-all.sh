#!/usr/bin/env bash

set -e
# set -x

./fitness.py \
  --ping \
  --ping-domain test.releng.mdc1.mozilla.com \
  -p releng-hardware \
  -t 75 \
  gecko-t-linux-talos-1804 "$@"
