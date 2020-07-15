# android-tools

tools for working with Android things at Mozilla

[![Build Status](https://travis-ci.com/mozilla-platform-ops/android-tools.svg?branch=master)](https://travis-ci.com/mozilla-platform-ops/android-tools)

## tool information

### adb_check_if_booted

Display if ADB finds a device booting and it's state in the process. `monitor_device` runs `adb_check_if_booted` regularly and prints it's output with a timestamp.

### bitbar_tc_queue_monitor

Display the Taskcluster Bitbar job queues.

### get_pending_jobs

Scans treeherder for pending jobs. Accepts filters for matching only certain jobs.

## installation

Symlink the scripts you'd like to use somewhere into your path.
