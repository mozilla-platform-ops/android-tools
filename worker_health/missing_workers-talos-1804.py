#!/usr/bin/env python3

import argparse

from worker_health import fitness

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        dest="log_level",
        default=0,
        help="specify multiple times for even more verbosity.",
    )
    args = parser.parse_args()

    # https://firefox-ci-tc.services.mozilla.com/provisioners/releng-hardware/worker-types/gecko-t-linux-talos-dw
    PROVISIONER = "releng-hardware"
    WORKER_TYPE = "gecko-t-linux-talos-1804"

    # TODO: populate from moonshot spreadsheet
    exclude_dict = {
        "t-linux64-ms-228": "nvme disk error",
        "t-linux64-ms-271": "too new of fw",
        "t-linux64-ms-272": "too new of fw",
        "t-linux64-ms-273": "too new of fw",
        "t-linux64-ms-274": "too new of fw",
        "t-linux64-ms-275": "too new of fw",
        "t-linux64-ms-276": "too new of fw",
        "t-linux64-ms-277": "too new of fw",
        "t-linux64-ms-278": "too new of fw",
        "t-linux64-ms-279": "too new of fw",
        "t-linux64-ms-280": "too new of fw",
    }

    f = fitness.Fitness(log_level=0, provisioner=PROVISIONER, alert_percent=85)
    f.moonshot_worker_report(WORKER_TYPE, args=args, exclude_dict=exclude_dict)
