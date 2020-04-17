#!/usr/bin/env bash

set -e
# set -x

# copies 3 manifest files in hu_* dirs to tree
# TODO: ensure there is one match to the wildcards...

# bring in common
. common.sh

mc_dir="$MC_CLIENT_PATH"

if [ -d ./hu_i686_* ]; then
  set -x
  cp \
    ./hu_i686_*/manifest.tt \
    $mc_dir/testing/config/tooltool-manifests/linux32/hostutils.manifest
  set +x
fi

if [ -d ./hu_x86_64_* ]; then
  set -x
  cp \
    ./hu_x86_64_*/manifest.tt \
    $mc_dir/testing/config/tooltool-manifests/linux64/hostutils.manifest
  set +x
fi

if [ -d ./hu_mac_* ]; then
  set -x
  cp \
    ./hu_mac_*/manifest.tt \
    $mc_dir/testing/config/tooltool-manifests/macosx64/hostutils.manifest
  set +x
fi

echo "success"
