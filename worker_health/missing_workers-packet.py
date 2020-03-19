#!/usr/bin/env python3

import argparse

import fitness
import quarantine

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    args = parser.parse_args()

    PROVISIONER = 'terraform-packet'
    WORKER_TYPE = 'gecko-t-linux'

    f = fitness.Fitness(
        log_level=0,
        provisioner=PROVISIONER,
        alert_percent=85,
    )
    q = quarantine.Quarantine()

    q.print_quarantined_workers(PROVISIONER, WORKER_TYPE)
    f.simple_worker_report(WORKER_TYPE, worker_count=70)
