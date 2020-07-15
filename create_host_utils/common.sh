#!/usr/bin/env bash

MC_CLIENT_PATH="/Users/$USER/hg/mozilla-source"



########################################################
########################################################
######## END USER EDITABLE SETTINGS
########################################################
########################################################

# TODO: check that MC_CLIENT_PATH is valid
if [ -z "$MC_CLIENT_PATH" ]; then
  echo "Please define MC_CLIENT_PATH!"
  exit 1
fi

if [ ! -e "$MC_CLIENT_PATH/config/milestone.txt" ]; then
  echo "Hmm, your mozilla-central client seems strange (missing config/milestone.txt)!"
  exit 1
fi

TOOLTOOL='python/mozbuild/mozbuild/action/tooltool.py'
TT_PATH="$MC_CLIENT_PATH/$TOOLTOOL"

# FFVER="66.0a1"
# FFVER="68.0a1"

# load version from config/milestone.txt in moz-central clone
FFVER=`cat $MC_CLIENT_PATH/config/milestone.txt | tail -n 1`
# echo $FFVER
