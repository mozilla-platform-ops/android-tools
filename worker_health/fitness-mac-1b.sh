#!/usr/bin/env bash

set -e
# set -x

./fitness_check.py "$@" -s  -a 0.75 -t 75 -p releng-hardware gecko-1-b-osx-1015
