#!/usr/bin/env python3

# drains host (quarantines and wait for jobs to finish),
#   runs a command, and then lifts the quarantine

from worker_health import runner

if __name__ == "__main__":
    runner.sr_main()
