# create_new_host_utils

If anything in this document is unclear, please see the reference document.

## reference

All of this is based on https://wiki.mozilla.org/Packaging_Android_host_utilities.

## steps

- edit common.sh to point to your mozilla-central client
- update the mozilla-central client that the coniguration points at
- remove old 'hu_*' directories
- create a new build script
  - `create_build_script.sh`
  - the script will output the new build script's name
- identify a good taskcluster build and configure script
  - find task IDs and URL for builds (see reference doc above for tips on picking)
    - ideally pick a job without retries on the build step. there's a known issue, see TODO section below.
  - enter the taskcluster ids for the selected build into the build script
- run the build script
  - comment out builds we're not ready for (I usually do linux first, then mac)
  - `./build_DATE.sh`
    - linux: if it fails with an error about not being able to find the artifact, see the comment on line 69 in the script
- compare new build to existing and sanity check
  - `./get_current.sh`
    - fetches all 3, no need to run for each
  - `./compare_versions.sh`
  - ensure things look good (same files, etc)
- `./upload.sh ARCH MESSAGE`
  - ARCH should be one of i686, x86_64, or mac
  - MESSAGE should be similar to "Bug 123456789: update linux hostutils"
- copy manifests to mozilla client, inspect, and commit
  - `./copy_manifests.sh`
  - cd to mozilla-central repo and `hg diff` to check that the size is close
  - commit change, make two separate PR's. one for mac, one for linux.
- run tests
  - see reference doc
- create phabricator diff
  - `moz-phab` or `arc diff`
  - add the treeherder link to your test run
  - if the tests look good, request a review

## TODO

- compare: output lines for programs other than araxis
- create_new_host_utils_linux.sh: handle bug
  - line 69: handle when the build isn't /0
- write report file with the manifest digests?
