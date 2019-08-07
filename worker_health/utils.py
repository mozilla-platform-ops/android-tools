import subprocess

from worker_health import logger


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
