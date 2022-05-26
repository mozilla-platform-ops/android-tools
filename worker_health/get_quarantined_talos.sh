#!/usr/bin/env bash

set -e
set -x

./quarantine_tool.py releng-hardware gecko-t-linux-talos show "$@"
