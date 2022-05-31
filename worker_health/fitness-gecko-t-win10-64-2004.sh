#!/usr/bin/env bash

set -e
# set -x

./fitness.py \
  -p releng-hardware \
  gecko-t win10-64-2004 "$@"
