#!/usr/bin/env bash

set -e
# set -x

# based on https://wiki.mozilla.org/Packaging_Android_host_utilities

# TODO: use https://pypi.org/project/htmllistparse/ to get latest build

# use gnu tar vs bsd tar... not sure if important (they do produce differently sized archives).
os=$(uname -s)
if [ "${os}" != "Darwin" ]; then
  echo "Please run on OS X!"
  exit 1
fi

# TODO: ensure URL doesn't have a trailing space

if [ -z "$1" ]; then
  echo "please provide a FTP url (like https://ftp.mozilla.org/pub/firefox/nightly/2019/01/2019-01-24-10-40-34-mozilla-central)"
  exit 1
fi
url=$1
arch='mac'


# bring in common
. common.sh

echo "FFVER: $FFVER"
echo "Current OS: $os"
echo "URL input: $url"
echo "Arch input: $arch"

url_base=$(basename "${url}")
dirname="hu_${arch}_${url_base}"

if [ -d "$dirname" ]; then
  echo "build for that ID already exists! exiting."
  exit 1
fi

mkdir "$dirname"
cd "$dirname"

# TODO: can't always assume 66.0a1
wget "${url}/firefox-${FFVER}.en-US.mac.common.tests.tar.gz"
wget "${url}/firefox-${FFVER}.en-US.mac.dmg"


## package

tar xf "firefox-${FFVER}.en-US.mac.common.tests.tar.gz" 'bin/*'
open "firefox-${FFVER}.en-US.mac.dmg"
# TODO: don't sleep (https://superuser.com/questions/878640/unix-script-wait-until-a-file-exists)
sleep 30
cp -R /Volumes/Firefox\ Nightly/Firefox\ Nightly.app/Contents/MacOS/* bin
cp -R /Volumes/Firefox\ Nightly/Firefox\ Nightly.app/Contents/Resources/* bin
# TODO: how to avoid prompt (needed if running automated build)
find bin -type f -perm +111 -print | grep -v \\. | xargs sudo codesign --force --deep --sign -
mv bin "host-utils-${FFVER}.en-US.mac"
# TODO: create hostutils_build_info file like other builds
tar cf "host-utils-${FFVER}.en-US.mac.tar" host-utils-"${FFVER}".en-US.mac/*
gzip "host-utils-${FFVER}.en-US.mac.tar"

# cleanup
umount /Volumes/Firefox\ Nightly

# tooltool
python3 "$TT_PATH" add --unpack --visibility public host-utils*.tar.gz

# show a report
find . -name manifest.tt -exec cat {} \;

# show success message
echo "SUCCESS"
