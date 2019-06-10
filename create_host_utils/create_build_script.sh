#!/usr/bin/env bash

set -e

date_string=`date +%Y%m%d%H%M`
filename="build_${date_string}.sh"

cat >> "$filename" <<EOL
#!/usr/bin/env bash

set -e

#
# build: $date_string
#
# bugzilla requesting new hostutils build: https://bugzilla.mozilla.org/show_bug.cgi?id=...
# build selected: https://treeherder.mozilla.org/#/jobs?repo=try&selectedJob=...
# - i686: 'Linux opt' on treeherder
# - x86_64: 'Linux x64 opt' on treeherder

#./create_new_host_utils_linux.sh TASK_ID i686
#./create_new_host_utils_linux.sh TASK_ID x86_64
#./create_new_host_utils_mac.sh BUILD_URL
EOL

chmod 755 $filename
echo $filename