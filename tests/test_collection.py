import os
import subprocess
import sys

import pytest

this_folder, this_file = os.path.split(__file__)

test_file_names = [name for name in os.listdir(this_folder) if name.endswith(".py")]
test_file_names.remove(this_file)
test_file_names.sort()


def forward_subprocess_output(e: subprocess.CalledProcessError):
    if e.stdout:
        print(e.stdout.decode("utf-8"), end="")
    if e.stderr:
        print(e.stderr.decode("utf-8"), end="", file=sys.stderr)


KNOWN_XFAIL = set(
    [
        "capture_multiplexer.py",
        "capture_circular.py",
        "check_timestamps.py",
        "drm_multiple_test.py",
        "multicamera_preview.py",
        "raw.py",
        "stack_raw.py",
    ]
)


def test_xfail_list():
    for xfail_name in KNOWN_XFAIL:
        assert (
            xfail_name in test_file_names
        ), f"XFAIL {xfail_name} not in test_file_names (remove it from KNOWN_XFAIL)"


# @pytest.mark.xfail(reason="Not validated to be working")
@pytest.mark.parametrize("test_file_name", test_file_names)
def test_file(test_file_name):
    print(sys.path)
    success = False
    process_env = os.environ.copy()
    process_env["LIBCAMERA_LOG_LEVELS"] = "*:DEBUG"

    try:
        subprocess.run(
            ["python", test_file_name],
            cwd=this_folder,
            env=process_env,
            timeout=20,
            capture_output=True,
            check=True,
        ).check_returncode()
        success = True
    except subprocess.TimeoutExpired as e:
        forward_subprocess_output(e)
    except subprocess.CalledProcessError as e:
        forward_subprocess_output(e)

    # Special handle the XFAIL tests
    if test_file_name in KNOWN_XFAIL:
        if success:
            pytest.fail(
                f"Test passed unexpectedly (needs removal from XFAIL list): {test_file_name}",
                pytrace=False,
            )
        else:
            if test_file_name in KNOWN_XFAIL:
                pytest.xfail(f"Known broken: {test_file_name}")

    if not success:
        pytest.fail(f"Test failed: {test_file_name}", pytrace=False)
