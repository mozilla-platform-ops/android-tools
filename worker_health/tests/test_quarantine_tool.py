import pathlib
import subprocess


def test_bin_quarantine_tool():  # config_fname, cleanup, print_all, force_pass, rcount, timeout):
    parent_dir = pathlib.Path(__file__).parent
    root_dir = parent_dir / ".."

    # Generate command
    cmd = ["./quarantine_tool.py", "-h"]

    # excute script
    pipe = subprocess.run(cmd, cwd=root_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert pipe.returncode == 0
