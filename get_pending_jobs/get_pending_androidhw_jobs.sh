#!/usr/bin/env bash

set -e
set -x

./get_pending_jobs.py --filter 'android-hw' "$@"
