#!/usr/bin/env bash

set -e
# set -x

# bring in common
. common.sh

# TODO: make diff tool configurable
echo "diff commands (manually run):"
echo ""

# see if araxis is present
araxis_present=0
if [ -x "$(command -v compare2)" ]; then
  araxis_present=1
fi

for arch in "${ARCHS[@]}"; do
  for dir in "./hu_${arch}_"*; do
    if [ -d "${dir}" ]; then
      echo "${arch}: "
      echo ""
      echo "  " diff "current/host-utils-*.en-US.*${arch}" "hu_${arch}_*/host-utils-${FFVER}.en-US.*${arch}"
      if [ "$araxis_present" -eq "1" ]; then
        echo "  " compare2 -swap "current/host-utils-*.en-US.*${arch}" "hu_${arch}_*/host-utils-${FFVER}.en-US.*${arch}"
      fi
      echo ""
    fi
  done
done
