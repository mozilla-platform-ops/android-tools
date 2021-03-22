#!/usr/bin/env bash

set -e
# set -x

# ./fitness.py -p releng-hardware gecko-t-linux-talos-dw $@

./fitness.py \
  --ping \
  --ping-domain test.releng.mdc1.mozilla.com \
  --ping-host rejh1.srv.releng.mdc1.mozilla.com \
  -p releng-hardware \
  -o \
  gecko-t-linux-talos-1804 "$@"
