#!/usr/bin/env python3

# runs a command with checkpoint
# - if you need to quarantine hosts, use safe_runner (this is not safe)

from worker_health import runner

if __name__ == "__main__":
    runner.ur_main()
