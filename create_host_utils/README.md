# create_new_host_utils

If anything in this document is unclear, please see the reference document.

## reference

All of this is based on https://wiki.mozilla.org/Packaging_Android_host_utilities.

## steps

- edit common.sh to point to your mozilla-central client
- update the mozilla-central client that the configuration points at
  - `hg pull`
  - `hg up central`
  - `hg glog`
    - ensure that the output shows a recent date (should be today).
    - if not, repeat `pull` and `up` and retest.
- create a new build script
  - `./generate_build_script.sh`
  - the script will output the new build script's name
- identify a good taskcluster build and edit the new build script
  - find task IDs and URL for builds (see reference doc above for tips on picking)
    - ideally pick a job without retries on the build step. there's a known issue, see TODO section below.
  - enter the taskcluster ids for the selected build into the build script
  - for mac: no trailing slash
- run the build script
  - remove old 'hu_*' build directories
    - `rm -rf ./hu_*`
  - comment out builds we're not ready for (I usually do linux first, then mac, then windows)
  - `./build_DATE.sh`
    - ensure that we're creating the version we expect (e.g. host-utils-116.0a1.en-US.mac.tar.gz)
      - if not, ensure m-c client is updated and common.sh points at the correct client
    - linux: if it fails with an error about not being able to find the artifact, see the comment on line 69 in the script
    - if it fails after examining the binary architecture, tooltool may be messed up. try running manually. on OS X, it may fail due to needing python2 still (https://bugzilla.mozilla.org/show_bug.cgi?id=1716390, fix noted in bug).
- compare new build to existing and sanity check
  - `./get_current.sh`
    - fetches all 3, no need to run for each os
  - `./compare_versions.sh`
    - ensure things look good
      - same directories
      - should mostly be binaries that change
- `./upload.sh ARCH MESSAGE`
  - ARCH should be one of x86_64, win32, or mac
  - MESSAGE should be similar to "Bug XYZ: update linux hostutils"
- copy manifests to mozilla client, inspect, and commit
  - make sure the mozilla client is on the tip of central
    - could be on an earlier hostutils change for another OS, etc
    - `hg up central` and verify with `hg wip` or `hg glog`
  - `./copy_manifests.sh`
  - inspect diff
    - cd to mozilla-central repo and `hg diff`
    - check that size is close
    - check that filename is correct arch and release
  - commit change and create review
    - make separate diffs for mac, linux, and windows
    - e.g. `hg commit -m 'Bug XYZ: update linux hostutils'
- create phabricator diff
  - `moz-phab --no-wip` (or `arc diff` in a pinch)
- run tests
  - see reference doc
  - add the treeherder link to the phab review
  - inspect tests
  - request reviews
    - linux and mac: gbrown (and requestor if PR-based)
    - win: gbrown (and requestor if PR-based) (mkato initially requested, but not active)
- repeat for other operating systems from 'run the build script' step

## TODO

- create_new_host_utils_linux.sh: handle bug
  - line 69: handle when the build isn't /0
- write report file with the manifest digests?
- see inline TODOs in the scripts
