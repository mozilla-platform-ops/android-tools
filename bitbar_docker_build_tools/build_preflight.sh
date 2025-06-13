#!/usr/bin/env bash
set -e

# check for stackdriver credds
if [ ! -e stackdriver_credentials.json ]; then
  echo "ERROR: please place stackdriver_credentials.json!"
  exit 1
else
  echo "- stackdriver credentials present: OK"
fi

# check for licenses dir
if [ ! -d licenses ]; then
  echo "ERROR: please place licenses directory with license files!"
  exit 1
else
  echo "- licenses dir exists: OK"
fi

./run_inspec_tests.sh

# what else?
echo ""
echo "SUCCESS: everthing looks good"
