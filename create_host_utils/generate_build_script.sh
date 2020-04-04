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
# notes on task ids:
# - x86_64: 'Linux x64 opt' on treeherder
# - i686: 'Linux opt' on treeherder
#
#X86_TASKID=""
#I686_TASKID=""

# STEP 3: uncomment and run desired builds
#
#./create_new_host_utils_linux.sh \$X86_TASKID x86_64 "\$BUILD_SELECTED"
#./create_new_host_utils_linux.sh \$I686_TASKID i686 "\$BUILD_SELECTED"
#./create_new_host_utils_mac.sh BUILD_URL
EOL

chmod 755 $filename
echo $filename