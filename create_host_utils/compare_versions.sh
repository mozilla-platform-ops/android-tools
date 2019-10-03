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

if [ -d ./hu_i686_* ]; then
  echo diff current/host-utils-*.en-US.linux-i686 hu_i686_*/host-utils-${FFVER}.en-US.linux-i686
  if [ "$araxis_present" -eq "1" ]; then
    echo ""
    echo compare2 -swap current/host-utils-*.en-US.linux-i686 hu_i686_*/host-utils-${FFVER}.en-US.linux-i686
  fi
fi
echo ""

if [ -d ./hu_x86_64_* ]; then
  echo diff current/host-utils-*.en-US.linux-x86_64 hu_x86_64_*/host-utils-$FFVER.en-US.linux-x86_64
  if [ "$araxis_present" -eq "1" ]; then
    echo ""
    echo compare2 -swap current/host-utils-*.en-US.linux-x86_64 hu_x86_64_*/host-utils-$FFVER.en-US.linux-x86_64
  fi
fi
echo ""

if [ -d ./hu_mac_* ]; then
  echo diff current/host-utils-*.en-US.mac hu_mac_*/host-utils-$FFVER.en-US.mac
  if [ "$araxis_present" -eq "1" ]; then
    echo ""
    echo compare2 -swap current/host-utils-*.en-US.mac hu_mac_*/host-utils-$FFVER.en-US.mac
  fi
fi
