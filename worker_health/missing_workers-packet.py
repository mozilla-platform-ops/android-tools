#!/usr/bin/env python3

import fitness

if __name__ == "__main__":

    f = fitness.Fitness(
        log_level=0,
        provisioner='terraform-packet',
        alert_percent=85,
    )

    worker_type = 'gecko-t-linux'
    f.simple_worker_report(worker_type)
