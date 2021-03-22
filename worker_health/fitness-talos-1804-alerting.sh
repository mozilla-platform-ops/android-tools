#!/usr/bin/env bash

set -e
# set -x

./fitness-talos-1804-all.sh \
  -o \
  -t 75 \
 "$@"
