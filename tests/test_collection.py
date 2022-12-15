import os
import subprocess
import sys

import pytest

this_folder, this_file = os.path.split(__file__)

test_file_names = [name for name in os.listdir(this_folder) if name.endswith(".py")]
test_file_names.remove(this_file)


def forward_subprocess_output(e: subprocess.CalledProcessError):
    print(e.stdout.decode("utf-8"), end="")
    print(e.stderr.decode("utf-8"), end="", file=sys.stderr)


@pytest.mark.xfail(reason="Test files are not yet implemented")
@pytest.mark.parametrize("test_file_name", test_file_names)
def test_file(test_file_name):
    success = False
    try:
        subprocess.run(
            ["python", test_file_name],
            cwd=this_folder,
            timeout=20,
            capture_output=True,
            check=True,
        ).check_returncode()
        success = True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        forward_subprocess_output(e)

    if not success:
        pytest.fail(f"Test failed: {test_file_name}")
