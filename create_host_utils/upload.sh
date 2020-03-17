#!/usr/bin/env bash

set -e
# set -x

# bring in common
. common.sh

if [ -z "$1" ]; then
  echo "ERROR: please provide an arch to upload (i686, x86_64, or mac)!"
  exit 1
fi
arch=$1

if [ -z "$2" ]; then
  echo "ERROR: please provide a commit message!"
  exit 1
fi
message=$2

if [ "$arch" == "i686" ]; then
  if [ -d ./hu_i686_* ]; then
    cd ./hu_i686_*
    $TT_PATH upload --authentication-file=~/.tooltool-tc-token --message $message
    cd ..
  fi
elif [ "$arch" == "x86_64" ]; then
  if [ -d ./hu_x86_64_* ]; then
    cd ./hu_x86_64_*
    $TT_PATH upload --authentication-file=~/.tooltool-tc-token --message $message
    cd ..
  fi
elif [ "$arch" == "mac" ]; then
  if [ -d ./hu_mac_* ]; then
    cd ./hu_mac_*
    $TT_PATH upload --authentication-file=~/.tooltool-tc-token --message $message
    cd ..
  fi
else
  echo "ERROR: invalid arch!"
  exit 1
fi
