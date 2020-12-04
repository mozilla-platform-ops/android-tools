#!/usr/bin/env bash

export MC_CLIENT_PATH="/Users/$USER/hg/mozilla-source-2"

export ARCHS=( "x86_64" "mac" "win32" )


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

export TOOLTOOL='python/mozbuild/mozbuild/action/tooltool.py'
export TT_PATH="$MC_CLIENT_PATH/$TOOLTOOL"

# FFVER="66.0a1"
# FFVER="68.0a1"

# load version from config/milestone.txt in moz-central clone
FFVER=$(tail -n 1 "${MC_CLIENT_PATH}/config/milestone.txt")
export FFVER
# echo $FFVER
