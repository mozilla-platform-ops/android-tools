#!/usr/bin/env python

import sys
import logging
import json

# import requests under python 2 or 3
try:
    import urllib.request as urllib_request  # for Python 3
except ImportError:
    import urllib2 as urllib_request  # for Python 2
import gzip

try:
    from tqdm import tqdm, trange
except:
    print("Please `pip install tqdm`.")
    sys.exit(1)

LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
DEFAULT_LOG_LEVEL = "WARNING"

REQUEST_DEBUGGING = False

if REQUEST_DEBUGGING:
    # These two lines enable debugging at httplib level (requests->urllib3->http.client)
    # You will see the REQUEST, including HEADERS and DATA, and RESPONSE with HEADERS but without DATA.
    # The only thing missing will be the response.body which is not logged.
    try:
        import http.client as http_client
    except ImportError:
        # Python 2
        import httplib as http_client
    http_client.HTTPConnection.debuglevel = 1

    # You must initialize logging, otherwise you'll not see debug output.
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


def get_json(an_url, log_level=3):
    req = urllib_request.Request(
        an_url,
        data=None,
        headers={
            "accept-encoding": "gzip,deflate",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:65.0) Gecko/20100101 Firefox/65.0",
        },
    )

    if log_level == 0:
        tqdm.write("Fetching %s... " % an_url)

    response = urllib_request.urlopen(req)
    result = gzip.decompress(response.read()).decode("utf-8")
    output = json.loads(result)
    return output


def get_push_pending_jobs(project, push_id, platform_filter=None, log_level=3):
    # TODO: check push health, if complete, we can exit here.

    ##### phase 2: get jobs for each push

    # data['results']

    # TODO: don't hardcode these (the field legend is provided at the end of all requests)
    # filtering for android-hw: fields 2, 15, 22
    #    2 is build platform
    #    15 is job_type_name (worker/test)
    #    22 is platform
    #   - seems like they all work
    #
    #       23 is pushid
    # field 26 is result (success, ???)
    # field 30 is state (completed, ???)
    key_pushid = 23
    key_platform = 22
    key_state = 30
    key_job_type_name = 15

    # https://treeherder.mozilla.org/api/project/mozilla-central/jobs/?return_type=list&count=2000&push_id=443884

    # https://treeherder.mozilla.org/api/project/mozilla-central/jobs/?return_type=list&count=2000&push_id=443884&offset=2000

    pending_jobs = 0
    iteration = 0
    while True:
        if iteration == 0:
            res = get_json(
                "https://treeherder.mozilla.org/api/project/%s/jobs/?return_type=list&count=2000&push_id=%s"
                % (project, push_id),
                log_level,
            )
        else:
            offset = iteration * 2000
            res = get_json(
                "https://treeherder.mozilla.org/api/project/%s/jobs/?return_type=list&count=2000&offset=%s&push_id=%s"
                % (project, offset, push_id),
                log_level,
            )
        result_count = len(res["results"])
        for item in res["results"]:
            # tqdm.write(item[30])
            if item[key_state] == "pending":
                if platform_filter:
                    if platform_filter in item[key_platform]:
                        pending_jobs += 1
                        if log_level == 0:
                            tqdm.write(
                                " - %s: %s"
                                % (item[key_platform], item[key_job_type_name])
                            )
                else:
                    # tqdm.write(item[key_job_type_name])
                    pending_jobs += 1
        iteration += 1
        # tqdm.write(result_count)
        if result_count != 2000:
            return pending_jobs
    # never reached!?!
    return pending_jobs


def get_pending_jobs(projects, filter=None, pages=4, page_size=50, early_exit=True):
    ####### phase 1: get try pushes
    last_seen_commit = ""
    results_dict = {}

    # TODO: multithread?
    proj_iterator = tqdm(projects, desc="projects")
    for project in proj_iterator:
        proj_iterator.set_postfix(project=project)
        pending_job_total = 0
        results_dict[project] = 0

        if log_level <= 1:
            tqdm.write("%s ---------------------------------------------" % project)

        # eventually?
        # while True:
        push_pbar = tqdm(total=page_size * pages, desc="pushes")
        for i in range(0, pages):
            pending_jobs_this_page = 0
            # TODO: figure out how to avoid overlap
            # url = "https://treeherder.mozilla.org/api/project/mozilla-central/push/"
            # https://treeherder.mozilla.org/api/project/mozilla-central/push/?full=true&count=10&fromchange=63bd1994e17c43e699c23f11ca01266d48e61d1e
            # https://treeherder.mozilla.org/api/project/mozilla-central/push/?full=true&count=11&push_timestamp__lte=1552211644
            if i != 0:
                url = (
                    "https://treeherder.mozilla.org/api/project/%s/push/?full=true&count=%s&tochange=%s"
                    % (project, page_size + 1, last_seen_commit)
                )
            else:
                url = (
                    "https://treeherder.mozilla.org/api/project/%s/push/?full=true&count=%s"
                    % (project, page_size)
                )

            output = get_json(url, log_level)
            # tqdm.write(output)

            results = output["results"]
            for result in results:
                last_seen_commit = result["revision"]
                #
                count = get_push_pending_jobs(project, result["id"], filter, log_level)
                # tqdm.write(count)
                pending_jobs_this_page += count
                pending_job_total += count
                #
                push_pbar.update(1)
                if log_level <= 1:
                    tqdm.write(
                        "%s:%s (%s): %s pending jobs"
                        % (result["id"], result["revision"], result["author"], count)
                    )

            results_dict[project] += pending_jobs_this_page

            if log_level == 0:
                tqdm.write("pending jobs this page: %s" % pending_jobs_this_page)
            # don't print this message if we're on the last page already
            if early_exit and i + 1 != pages and pending_jobs_this_page == 0:
                tqdm.write(
                    "%s: page %s: no pending jobs found on this page, stopping search early."
                    % (project, i + 1)
                )
                break
            pending_jobs_this_page = 0
        # TODO: print a summary of this project's pending jobs?
        push_pbar.close()
    return results_dict


if __name__ == "__main__":
    import argparse

    PAGE_SIZE = 20
    PAGES = 3

    parser = argparse.ArgumentParser(
        usage="%(prog)s [options]",
        description="Scan treeherder to get a count of pending jobs.",
    )
    # TODO: make this take a csv vs a single
    parser.add_argument(
        "--project",
        "-p",
        help="a single project to inspect for pending jobs (defaults to use mozilla-inbound, autoland, try, and mozilla-central)",
    )
    parser.add_argument(
        "--filter", "-f", help="require pending jobs to match this string"
    )
    parser.add_argument(
        "--page-size",
        default=PAGE_SIZE,
        dest="page_size",
        type=int,
        help="how many results per page to fetch (default is %s)" % PAGE_SIZE,
    )
    parser.add_argument(
        "--pages",
        default=PAGES,
        type=int,
        help="how many pages of results should we inspect (default is %s)" % PAGES,
    )
    parser.add_argument(
        "-n",
        "--no-early-exit",
        dest="no_early_exit",
        action="store_true",
        help="don't exit early if no pending jobs found on a page",
    )
    # handle multiple -v args (like -vvv)
    parser.add_argument(
        "--verbose", "-v", action="append_const", dest="log_level", const=-1
    )

    args = parser.parse_args()
    log_level = LOG_LEVELS.index(DEFAULT_LOG_LEVEL)

    early_exit = True
    if args.no_early_exit:
        early_exit = False

    # For each "-q" and "-v" flag, adjust the logging verbosity accordingly
    # making sure to clamp off the value from 0 to 4, inclusive of both
    for adjustment in args.log_level or ():
        log_level = min(len(LOG_LEVELS) - 1, max(log_level + adjustment, 0))

    log_level_name = LOG_LEVELS[log_level]
    # tqdm.write(log_level)
    # sys.exit()

    # # TODO: sanity check args.project
    if args.project:
        projects = [args.project]
    else:
        projects = ["try", "mozilla-inbound", "autoland", "mozilla-central"]

    if args.filter:
        results_dict = get_pending_jobs(
            projects, args.filter, args.pages, args.page_size, early_exit
        )
    else:
        results_dict = get_pending_jobs(
            projects, args.filter, args.pages, args.page_size, early_exit
        )

    # display a final summary of results
    tqdm.write("")
    grand_total = 0
    filter_string = ""
    if args.filter:
        filter_string = "'%s' " % args.filter
    for key in results_dict:
        grand_total += results_dict[key]
        tqdm.write("%s: pending %sjobs: %s" % (key, filter_string, results_dict[key]))
    if len(projects) > 1:
        tqdm.write("total: pending %sjobs: %s" % (filter_string, grand_total))
