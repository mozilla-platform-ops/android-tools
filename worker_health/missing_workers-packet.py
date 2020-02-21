#!/usr/bin/env python3

import argparse

import fitness

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    args = parser.parse_args()

    f = fitness.Fitness(
        log_level=0,
        provisioner='terraform-packet',
        alert_percent=85,
    )

    worker_type = 'gecko-t-linux'
    f.simple_worker_report(worker_type, worker_count=70)
