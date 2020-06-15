#!/usr/bin/env bash

set -e

date_string=`date +%Y%m%d%H%M`
filename="build_${date_string}.sh"

cat >> "$filename" <<EOL
#!/usr/bin/env bash

set -e

#
# build script creation date: $date_string
#

# STEP 1: uncomment and enter the build you've selected
#
#BUILD_SELECTED="https://treeherder.mozilla.org/#/jobs?repo=mozilla-central&revision=..."

# STEP 2: Uncomment and set TASK_IDs.
#
# notes on task id and build url:
# - x86_64: 'Linux x64 opt' on treeherder
# - win32: 'Windows 2012 opt' on treeherder
# - mac: see https://wiki.mozilla.org/Packaging_Android_host_utilities#macOS
# X86_TASKID=""
# WIN_TASKID=""
# MAC_BUILD_URL=""

# STEP 3: uncomment and run desired builds
#
# ./create_new_host_utils_linux.sh \$X86_TASKID x86_64 "\$BUILD_SELECTED"
# ./create_new_host_utils_win.sh \$WIN_TASKID win "\$BUILD_SELECTED"
# ./create_new_host_utils_mac.sh "\$MAC_BUILD_URL"
EOL

chmod 755 $filename
echo $filename