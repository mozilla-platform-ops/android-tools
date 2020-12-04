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

# if [ -d ./hu_i686_* ]; then
#   echo "i686: "
#   echo ""
#   echo "  " diff current/host-utils-*.en-US.linux-i686 hu_i686_*/host-utils-${FFVER}.en-US.linux-i686
#   if [ "$araxis_present" -eq "1" ]; then
#     echo "  " compare2 -swap current/host-utils-*.en-US.linux-i686 hu_i686_*/host-utils-${FFVER}.en-US.linux-i686
#   fi
#   echo ""
# fi

# if [ -d ./hu_x86_64_* ]; then
#   echo "x86_64: "
#   echo ""
#   echo "  " diff current/host-utils-*.en-US.linux-x86_64 hu_x86_64_*/host-utils-$FFVER.en-US.linux-x86_64
#   if [ "$araxis_present" -eq "1" ]; then
#     echo "  " compare2 -swap current/host-utils-*.en-US.linux-x86_64 hu_x86_64_*/host-utils-$FFVER.en-US.linux-x86_64
#   fi
#   echo ""
# fi

# if [ -d ./hu_mac_* ]; then
#   echo "Mac: "
#   echo ""
#   echo "  " diff current/host-utils-*.en-US.mac hu_mac_*/host-utils-$FFVER.en-US.mac
#   if [ "$araxis_present" -eq "1" ]; then
#     echo "  " compare2 -swap current/host-utils-*.en-US.mac hu_mac_*/host-utils-$FFVER.en-US.mac
#   fi
#   echo ""
# fi

archs=( "x86_64" "mac" "win32" )
for arch in "${archs[@]}"; do
  for dir in "./hu_${arch}_"*; do
    if [ -d "${dir}" ]; then
      # arch="win32"
      echo "${arch}: "
      echo ""
      echo "  " diff "current/host-utils-*.en-US.${arch}" "hu_${arch}_*/host-utils-${FFVER}.en-US.${arch}"
      if [ "$araxis_present" -eq "1" ]; then
        echo "  " compare2 -swap "current/host-utils-*.en-US.${arch}" "hu_${arch}_*/host-utils-${FFVER}.en-US.${arch}"
      fi
      echo ""
    fi
  done
done
