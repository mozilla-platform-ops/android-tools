#!/usr/bin/env bash

set -e

RONIN_INVENTORY_DIR=$HOME/git/ronin_puppet/inventory.d

# notes:
#   - `-r` mode takes a sr/ur resume dir as an argument and
#      updates `remaining_hosts` in the state file.
#   - `-t` mode outputs the remaining_hosts key/value as text

# this excludes signing hosts, as they require duo auth and runner fails with them
./extract_targets.py \
  `# kept on old strange stuff` \
  -i nss \
  -i vpn \
  `# access is controlled and we don't control the config` \
  -i signing \
  `# in services.yaml` \
  -i deploystudio \
  "$RONIN_INVENTORY_DIR"/*.yaml \
  -t "$@"
  # -r "$@"
