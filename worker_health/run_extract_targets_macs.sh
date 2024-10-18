#!/usr/bin/env bash

set -e

RONIN_INVENTORY_DIR=$HOME/git/ronin_puppet/inventory.d

# notes:
#   - `-r` mode takes a sr/ur resume dir as an argument and
#      updates `remaining_hosts` in the state file.
#   - `-t` mode outputs the remaining_hosts key/value as text

# this excludes signing hosts, as they require duo auth and runner fails with them
./extract_targets.py \
  "$RONIN_INVENTORY_DIR"/macmini-m1.yaml \
  "$RONIN_INVENTORY_DIR"/macmini-m2.yaml \
  "$RONIN_INVENTORY_DIR"/macmini-r8.yaml \
  "$RONIN_INVENTORY_DIR"/services.yaml \
  -r "$@"
  # -t "$@"
