import os
from distutils import dir_util

from pytest import fixture

from worker_health import runner


@fixture
def datadir(tmpdir, request):
    """
    Fixture responsible for searching a folder with the same name of test
    module and, if available, moving all contents to a temporary directory so
    tests can use them freely.
    """
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)

    if os.path.isdir(test_dir):
        dir_util.copy_tree(test_dir, str(tmpdir))

    return tmpdir


def test_get_host_counts_general(datadir):
    confdir = datadir.join("general")
    r = runner.Runner.from_resume(confdir)
    assert r.get_host_counts() == {"skipped": 0, "completed": 3, "failed": 0, "remaining": 0, "total": 3, "to_skip": 1}


def test_get_host_counts_general2(datadir):
    confdir = datadir.join("general2")
    r = runner.Runner.from_resume(confdir)
    assert r.get_host_counts() == {"skipped": 1, "completed": 1, "failed": 1, "remaining": 4, "total": 7, "to_skip": 1}
