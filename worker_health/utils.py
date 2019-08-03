import subprocess

from worker_health import logger


class NonZeroExit(Exception):
    pass


def run_cmd(cmd):
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    proc.wait(timeout=10)
    rc = proc.returncode
    if rc == 0:
        tmp = proc.stdout.read().strip()
        return tmp.decode()
    else:
        raise NonZeroExit("non-zero code returned")


def bitbar_systemd_service_present(warn=False, error=False):
    try:
        run_cmd("systemctl status bitbar > /dev/null 2>&1")
    except NonZeroExit:
        if warn:
            logger.warn(
                "this should be run on the primary devicepool host for maximum data."
            )
        if error:
            logger.error("this must be run on the primary devicepool host!")
        return False
    return True
