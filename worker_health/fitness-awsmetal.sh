#!/usr/bin/env bash

set -e
set -x

# ./fitness.py -p terraform-packet | grep -E 'alert|workers'
#./fitness.py -p terraform-packet $@ | grep -E 'alert|workers'
./fitness.py -p gecko-t -s -o t-linux-metal $@

# gecko-t/t-linux-metal jobs
