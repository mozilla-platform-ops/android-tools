#!/usr/bin/env bash

set -e
# set -x

# create_new_host_utils

TC_ROOT='https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task'
info_string=""


function check_arch {
  file_arch="$(file firefox/ssltunnel)"
  if [ "$arch" = "x86_64" ]; then
    if [[ "$file_arch" =~ "ELF 64-bit" ]]; then
      echo "* examined binary's arch is good"
    else
      exit 1
    fi
  elif [ "$arch" == "i686" ]; then
    if [[ "$file_arch" =~ "ELF 32-bit" ]]; then
      echo "* examined binary's arch is good"
    else
      exit 1
    fi
  else
    echo "invalid ARCH specified ($arch)!"
    exit 1
  fi
}


# TODO: reorder and rename to clarify what values are from the hostutils build host vs the firefox build
# TODO: pull this out into common
function set_info_string {
    info_string+="FFVER: $FFVER\n"
    info_string+="Current OS: $os\n"
    info_string+="Build used: $build_used\n"
    info_string+="Build ID input: $task_id\n"
    info_string+="Arch input: $arch\n"
}


# use gnu tar vs bsd tar... not sure if important (they do produce differently sized archives).
os=$(uname -s)
# if [ "${os}" != "Linux" ]; then
#   echo "Please run on linux!"
#   exit 1
# fi

# TODO: take a TC push id and do all 3 archs (mac, x86, x86_64)
# TODO: use xz vs gz? better compression.
# TODO: fetch buildhub.json for the build and extract the milestone/version (e.g. 66.0a1)
#   - reflects config/milestone.txt aka current nightly version

## arg requirements
if [ -z "$1" ]; then
  echo "please provide a task id"
  exit 1
fi
task_id=$1

if [ -z "$2" ]; then
  echo "please provide an arch (i686 or x86_64)"
  exit 1
fi
arch=$2

if [ -z "$3" ]; then
  echo "please provide an the URL of the build used"
  exit 1
fi
build_used=$3

## arg checking
if [ "$arch" != "i686" ] && [ "$arch" != "x86_64" ]; then
  echo "invalid arch"
  exit 1
fi

# bring in common
. common.sh
# set info string
set_info_string

echo ""
echo "-------------------------------"
printf '%b' "$info_string"
echo "-------------------------------"
echo ""

dirname="hu_${arch}_${task_id}"

if [ -d "$dirname" ]; then
  echo "build for that ID already exists! exiting."
  exit 1
fi

mkdir "$dirname"
cd "$dirname"

## fetch inputs

# example url to get artifacts:
#    https://queue.taskcluster.net/v1/task/f0YF3AX8Sb2pAJ3-hATItg/runs/0/artifacts/public/build/target.tar.bz2
#
# things to get: target.tar.bz2 target.common.tests.tar.gz

# TODO: check runs/1, runs/2, etc if runs/0 has error (means first build didn't start and was retried)
run_id=0
wget "${TC_ROOT}/${task_id}/runs/$run_id/artifacts/public/build/target.tar.bz2"
wget "${TC_ROOT}/${task_id}/runs/$run_id/artifacts/public/build/target.common.tests.tar.gz"

## package host_utils

# commands from https://wiki.mozilla.org/Packaging_Android_host_utilities

mkdir 'temp_common'
# TODO: add a flag to enable/disable tar -v
tar xf target.tar.bz2
tar xf target.common.tests.tar.gz -C 'temp_common'
rm firefox/firefox*
rm -r firefox/browser
mv 'temp_common'/bin/* firefox
# write out info file
printf '%b' "$info_string" > firefox/.hostutils_build_info
# double check arch of binary
echo ""
echo "-------------------------------"
check_arch
echo "-------------------------------"
echo ""
mv firefox "host-utils-${FFVER}.en-US.linux-${arch}"
tar cf "host-utils-${FFVER}.en-US.linux-${arch}.tar" "host-utils-${FFVER}.en-US.linux-${arch}"
gzip "host-utils-${FFVER}.en-US.linux-${arch}.tar"

# tooltool
python3 "$TT_PATH" add --unpack --visibility public host-utils*.tar.gz

# show a report
 find . -name manifest.tt -exec cat {} \;

# show success message
echo ""
echo "SUCCESS"
