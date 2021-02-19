#!/usr/bin/env python

import argparse
import quarantine

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    args = parser.parse_args()

    # TODO: add args

    q = quarantine.Quarantine()
    q.main_get_quarantined()
