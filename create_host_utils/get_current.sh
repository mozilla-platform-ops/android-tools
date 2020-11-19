#!/usr/bin/env bash

set -e
set -

# bring in common
. common.sh

mc_dir="$MC_CLIENT_PATH"

# TODO: delete existing current directory? seems wise

mkdir -p current
cd current

"$TT_PATH" fetch -m "$mc_dir/testing/config/tooltool-manifests/linux64/hostutils.manifest"
"$TT_PATH" fetch -m "$mc_dir/testing/config/tooltool-manifests/macosx64/hostutils.manifest"
"$TT_PATH" fetch -m "$mc_dir/testing/config/tooltool-manifests/win32/hostutils.manifest"
