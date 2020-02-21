#!/usr/bin/env bash

set -e

# ./fitness.py -p terraform-packet | grep -E 'alert|workers'
./fitness.py $@ | grep -E 'alert|workers queried'
