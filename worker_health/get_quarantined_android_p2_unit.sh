#!/usr/bin/env bash

set -e
set -x

./quarantine_tool.py proj-autophone gecko-t-bitbar-gw-unit-p2 show "$@"
