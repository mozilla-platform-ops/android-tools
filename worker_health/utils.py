import json
import pprint
import requests
import subprocess

from worker_health import logger

USER_AGENT_STRING = "Python (https://github.com/mozilla-platform-ops/android-tools/tree/master/worker_health)"

def run_cmd(cmd):
    return (
        subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        .strip()
        .decode()
    )


def bitbar_systemd_service_present(warn=False, error=False):
    try:
        run_cmd("systemctl status bitbar > /dev/null 2>&1")
    except subprocess.CalledProcessError:
        if warn:
            logger.warn(
                "this should be run on the primary devicepool host for maximum data."
            )
        if error:
            logger.error("this must be run on the primary devicepool host!")
        return False
    return True

# handles continuationToken
def get_jsonc(an_url, verbosity=0):
    output_dict = {}
    headers = {"User-Agent": USER_AGENT_STRING}
    retries_left = 2

    while retries_left >= 0:
        if verbosity > 2:
            print(an_url)
        response = requests.get(an_url, headers=headers)
        result = response.text
        try:
            output = json.loads(result)
            # will only break on good decode
            break
        except json.decoder.JSONDecodeError as e:
            logger.warning("json decode error. input: %s" % result)
            if retries_left == 0:
                raise e
        retries_left -= 1
    output_dict = output

    while "continuationToken" in output:
        payload = {"continuationToken": output["continuationToken"]}
        if verbosity > 2:
            print("CONT %s, %s" % (an_url, output["continuationToken"]))
        response = requests.get(an_url, headers=headers, params=payload)
        result = response.text
        output = json.loads(result)
        # tc messes with us and sends back and empty workers array
        if 'workers' in output and len(output['workers']):
            output_dict.update(output)

    if verbosity > 2:
            pprint.pprint(output_dict)
    return output_dict
