#!/usr/bin/env python3

# Idea: We have X hosts in quarantine. Let them run one job and then see if
# they're better, if not quarantine them again.
#
# - Detects if there are pending jobs and only runs then?
# - Maybe always put them back in quarantine after one job and present a report?

# v0: single host
# - take single host as input
# - check that there are jobs to run
# - record current state of host
# - remove from quarantine
# - wait for job to start
# - place back in quarantine (done immediately so only single job runs)
# - loop until the job is done
# - record current state of host
# - record sucess/failure for host

# v1: multiple hosts
# step 1: take list of quarantined hosts
# step 2: repeat v0 over all hosts
# step 3: show report

# v2: advanced
# step 1: gather quarantined hosts
