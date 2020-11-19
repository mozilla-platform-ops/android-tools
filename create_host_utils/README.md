# create_new_host_utils

If anything in this document is unclear, please see the reference document.

## reference

All of this is based on https://wiki.mozilla.org/Packaging_Android_host_utilities.

## steps

- edit common.sh to point to your mozilla-central client
- update the mozilla-central client that the configuration points at
  - `h up central`
  - `h pull`
- remove old 'hu_*' directories
- create a new build script
  - `./generate_build_script.sh`
  - the script will output the new build script's name
- identify a good taskcluster build and edit script
  - find task IDs and URL for builds (see reference doc above for tips on picking)
    - ideally pick a job without retries on the build step. there's a known issue, see TODO section below.
  - enter the taskcluster ids for the selected build into the build script
  - for mac: no trailing slash
- run the build script
  - comment out builds we're not ready for (I usually do linux first, then mac)
  - `./build_DATE.sh`
    - linux: if it fails with an error about not being able to find the artifact, see the comment on line 69 in the script
- compare new build to existing and sanity check
  - `./get_current.sh`
    - fetches all 3, no need to run for each
  - `./compare_versions.sh`
    - ensure things look good
      - same directories
      - should mostly be binaries that change
- `./upload.sh ARCH MESSAGE`
  - ARCH should be one of x86_64, win32, or mac
  - MESSAGE should be similar to "Bug 123456789: update linux hostutils"
- copy manifests to mozilla client, inspect, and commit
  - make sure the mozilla client is on the tip of central
    - could possibly be on the linux hostutils change you did earlier
  - `./copy_manifests.sh`
  - cd to mozilla-central repo and `hg diff` to check that the size is close
  - commit change and create review
    - make separate diffs for mac and linux
- create phabricator diff
  - `moz-phab` or `arc diff`
- run tests
  - see reference doc
  - add the treeherder link to the phab review
  - if the tests look good, request a review from gbrown

## TODO

- compare: output lines for programs other than araxis
- create_new_host_utils_linux.sh: handle bug
  - line 69: handle when the build isn't /0
- write report file with the manifest digests?
