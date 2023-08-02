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
    confdir_1 = datadir.join("general")
    r = runner.Runner.from_resume(confdir_1)
    assert r.get_host_counts() == {"completed": 3, "failed_hosts": 0, "remaining": 0}
