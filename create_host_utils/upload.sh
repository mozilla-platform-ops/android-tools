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

if [ -d ./hu_${arch}_* ]; then
  cd ./hu_${arch}_*
  $TT_PATH upload --authentication-file=~/.tooltool-tc-token --message $message
  cd ..
else
  echo "ERROR: dir not found! './hu_${arch}_*'"
  exit 1
fi

echo ""
echo "SUCCESS"
