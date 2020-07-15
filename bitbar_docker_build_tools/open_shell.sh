#!/usr/bin/env bash

set -e

# docker run -it --entrypoint '/bin/bash' test-docker

root_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

if [ -d "$root_dir/tests" ]; then
  TESTDIR_MOUNTPOINT="-v $root_dir/tests:/tests"
fi

SRCDIR_LOCATION="${HOME}/hg/mozilla-source"
if [ -d "$SRCDIR_LOCATION" ]; then
  SRCDIR_MOUNTPOINT="-v ${SRCDIR_LOCATION}:/source"
fi

# TODO: mount mozilla source in
# -v $HOME/hg/mozilla-source:/source

# scrapyard
#
# -e GENERIC_WORKER_CONF='generic-worker'
  # -e LIVELOG_SECRET='abc123' \
    # --tmpfs /builds \
#  -p 5037:5037 \
#  --expose 5037 \
#  --network=host \  # doesn't work on mac

docker run -u root \
  -e DEVICE_NAME='aje-test' \
  -e TC_WORKER_TYPE='gecko-t-ap-test-g5' \
  -e TC_WORKER_GROUP='bitbar' \
  -e TASKCLUSTER_CLIENT_ID='project/autophone/bitbar-x-test-g5' \
  -e TASKCLUSTER_ACCESS_TOKEN='not_a_real_secret' \
  -e gecko_t_ap_test_g5="SECRET_SECRET_SECRET_DO NOT LEAK 1" \
  -e TESTDROID_APIKEY="SECRET_SECRET_SECRET_DO NOT LEAK 2" \
  -it --entrypoint '/bin/bash' \
  $TESTDIR_MOUNTPOINT \
  $SRCDIR_MOUNTPOINT \
  test-docker
