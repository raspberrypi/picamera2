import os
import subprocess
import sys

import numpy as np
import pytest

from picamera2 import Picamera2
from picamera2.picamera2 import CameraManager

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
        "capture_circular_nooutput.py",
        "capture_circular_stream.py",
        "capture_circular.py",
        "capture_dng_and_jpeg_helpers.py",
        "capture_dng.py",
        "capture_image_full_res.py",
        "capture_mjpeg_timestamp.py",
        "capture_mjpeg_v4l2.py",
        "capture_mjpeg.py",
        "capture_multiplexer.py",
        "capture_stream_udp.py",
        "capture_stream.py",
        "capture_timelapse_video.py",
        "capture_video_raw.py",
        "capture_video_timestamp.py",
        "capture_video.py",
        "check_timestamps.py",
        "display_transform_null.py",
        "drm_multiple_test.py",
        "encoder_start_stop.py",
        "large_datagram.py",
        "mjpeg_server.py",
        "mode_test.py",
        "multicamera_preview.py",
        "multiple_quality_capture.py",
        "pick_mode.py",
        "rotation.py",
        "stack_raw.py",
        "still_during_video.py",
        "video_with_config.py",
    ]
)


def test_xfail_list():
    for xfail_name in KNOWN_XFAIL:
        assert (
            xfail_name in test_file_names
        ), f"XFAIL {xfail_name} not in test_file_names"


# @pytest.mark.xfail(reason="Not validated to be working")
@pytest.mark.parametrize("test_file_name", test_file_names)
def test_file(test_file_name):
    print(sys.path)
    success = False
    try:
        subprocess.run(
            ["python", test_file_name],
            cwd=this_folder,
            timeout=60,
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
