#!/usr/bin/env bash

set -e
# set -x

./fitness_check.py "$@" -s -o -t 75 -p releng-hardware gecko-t-osx-1015-r8
