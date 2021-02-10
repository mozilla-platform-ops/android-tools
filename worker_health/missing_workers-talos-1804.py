#!/usr/bin/env python3

import argparse
import sys

import fitness
import quarantine

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    args = parser.parse_args()

    PROVISIONER = "releng-hardware"
    WORKER_TYPE = "gecko-t-linux-talos-1804"

    print("not implemented yet")
    sys.exit(0)

    f = fitness.Fitness(log_level=0, provisioner=PROVISIONER, alert_percent=85)
    q = quarantine.Quarantine()

    q.print_quarantined_workers(PROVISIONER, WORKER_TYPE)
    f.simple_worker_report(WORKER_TYPE, worker_count=12)


# https://firefox-ci-tc.services.mozilla.com/provisioners/releng-hardware/worker-types/gecko-t-linux-talos-dw
