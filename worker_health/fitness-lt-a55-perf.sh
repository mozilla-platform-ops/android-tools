#!/usr/bin/env bash

set -e
# set -x

#./fitness_check.py "$@" -s -o -t 75

# all, sorted by SR
./fitness_check.py gecko-t-lambda-perf-a55 -s "$@"
