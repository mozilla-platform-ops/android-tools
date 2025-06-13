#!/usr/bin/env bash

# we want cleanup to run even if tests failed
# - use true on test cmd
set -e
# set -x

name="devicepool-inspec-testing"

docker run \
    --name $name \
    -u root \
    -e DEVICE_NAME='aje-test' \
    -e TC_WORKER_TYPE='gecko-t-ap-test-g5' \
    -e TC_WORKER_GROUP='bitbar' \
    -e TASKCLUSTER_CLIENT_ID='project/autophone/bitbar-x-test-g5' \
    -e TASKCLUSTER_ACCESS_TOKEN='not_a_real_secret' \
    -e gecko_t_ap_test_g5="NOT_A_SECRET" \
    -e TESTDROID_APIKEY="NOT_A_SECRET_2 # pragma: allowlist secret" \
    -d -t devicepool

# TODO: run test
inspec exec image_tests -t docker://$name || true

# TODO: tear down
docker stop $name
docker rm $name
