#!/usr/bin/env python3

import argparse
import json
import os
import pprint
import sys

import taskcluster


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # parser.add_argument(
    #     "-v",
    #     "--verbose",
    #     action="count",
    #     default=False,
    #     help="specify multiple times for even more verbosity",
    # )
    # parser.add_argument("-d", "--daemon-mode", action="store_true")
    parser.add_argument("search_term", type=str, help="string to search for")
    args = parser.parse_args()

    # lambdas for colored text
    fg = lambda text, color: "\33[38;5;" + str(color) + "m" + text + "\33[0m"
    bg = lambda text, color: "\33[48;5;" + str(color) + "m" + text + "\33[0m"

    search_term = args.search_term

    with open(os.path.expanduser("~/.tc_quarantine_token")) as json_file:
        data = json.load(json_file)
    root_url = "https://firefox-ci-tc.services.mozilla.com"
    creds = {"clientId": data["clientId"], "accessToken": data["accessToken"]}

    queue = taskcluster.Queue({"rootUrl": root_url, "credentials": creds})

    p_count = 0
    wt_count = 0
    m_count = 0
    for item in queue.listProvisioners()["provisioners"]:
        p_count += 1
        provisioner_id = item["provisionerId"]
        if search_term in provisioner_id:
            m_count += 1
            print(
                "https://firefox-ci-tc.services.mozilla.com/provisioners/%s"
                % fg(provisioner_id, 13)
            )
        for wt in queue.listWorkerTypes(provisioner_id)["workerTypes"]:
            wt_count += 1
            worker_type = wt["workerType"]
            # import pdb; pdb.set_trace()
            if search_term in worker_type:
                m_count += 1
                print(
                    "https://firefox-ci-tc.services.mozilla.com/provisioners/%s/worker-types/%s"
                    % (provisioner_id, fg(worker_type, 14))
                )
    print(
        "%s matches, scanned %s provisionerIds and %s workerTypes"
        % (m_count, p_count, wt_count)
    )
