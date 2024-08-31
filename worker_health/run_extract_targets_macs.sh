#!/usr/bin/env bash

set -e

RONIN_INVENTORY_DIR=/Users/aerickson/git/ronin_puppet/inventory.d

./extract_targets.py \
  $RONIN_INVENTORY_DIR/macmini-m1.yaml \
  $RONIN_INVENTORY_DIR/macmini-m2.yaml \
  $RONIN_INVENTORY_DIR/macmini-r8.yaml \
  $RONIN_INVENTORY_DIR/services.yaml \
   -r "$@"
