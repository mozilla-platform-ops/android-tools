#!/usr/bin/env bash

set -e
set -x

./get_quarantined.py releng-hardware gecko-t-linux-talos "$@"
