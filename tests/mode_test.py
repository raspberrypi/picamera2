#!/usr/bin/python3

# Test that we can read the sensor modes, and then configure the camera
# into each mode and get the correct framerate

from picamera2 import Picamera2
from picamera2.sensor_format import SensorFormat
from libcamera import Transform
import time
from math import isclose

picam2 = Picamera2()


def check(raw_config, fps):
    # Don't bother checking anything over 5MP, as that may cause buffer issues
    if raw_config["size"][0] * raw_config["size"][1] > 5e6:
        print("Not checking", raw_config)
        return
    picam2.video_configuration = picam2.create_video_configuration(
        raw=raw_config,
    )
    picam2.configure("video")
    # Check we got the correct raw format
    assert picam2.camera_configuration()["raw"]["size"] == raw_config["size"]
    set_format = SensorFormat(picam2.camera_configuration()["raw"]["format"])
    set_format.transform(Transform(rotation=picam2.camera_properties["Rotation"]))
    assert (
        set_format.format == raw_config["format"]
    ), f'{picam2.camera_configuration()["raw"]["format"]} != {raw_config["format"]}'
    picam2.set_controls({"FrameRate": fps})
    picam2.start(show_preview=True)
    time.sleep(1)
    # Check we got roughly the right framerate
    metadata = picam2.capture_metadata()
    framerate = 1000000 / metadata["FrameDuration"]
    print(metadata)
    print(f"Framerate: {framerate:.2f}, requested: {fps:.2f}")
    assert isclose(framerate, fps, abs_tol=1.0)
    picam2.stop()


modes = picam2.sensor_modes
# Make sure less than 5 modes, to avoid timing out
modes = modes[:5]
for mode in modes:
    # Check packed mode works
    check({"size": mode["size"], "format": mode["format"].format}, mode["fps"])
    # Check unpacked mode works
    check({"size": mode["size"], "format": mode["unpacked"]}, mode["fps"])
