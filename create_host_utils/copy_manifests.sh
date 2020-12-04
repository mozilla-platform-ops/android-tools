#!/usr/bin/env bash

set -e
# set -x

# copies manifest files in hu_* dirs to tree
# TODO: ensure there is one match to the wildcards...

# bring in common
. common.sh

for arch in "${ARCHS[@]}"; do
  for dir in "./hu_${arch}_"*; do
    if [ -d "${dir}" ]; then
      case "${arch}" in
        "win32")
          destdir="${arch}"
          ;;
        "mac")
          destdir="macosx64"
          ;;
        "x86_64")
          destdir="linux64"
          ;;
        *)
          echo "got an unknown arch ${arch}"
          exit 1
          ;;
      esac
      set -x
      cp ./hu_"${arch}"_*/manifest.tt "${MC_CLIENT_PATH}/testing/config/tooltool-manifests/${destdir}/hostutils.manifest"
      set +x
    fi
  done
done

echo "success"
