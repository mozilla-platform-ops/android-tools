#!/usr/bin/env bash

set -e
set -x

pipenv run ./quarantine_tool.py releng-hardware gecko-t-linux-talos-1804 "$@"
