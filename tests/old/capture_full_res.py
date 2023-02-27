#!/usr/bin/python3
# Capture a JPEG while still running in the preview mode.
import os
from tempfile import TemporaryDirectory

from scicamera import Camera, CameraConfig
from scicamera.configuration import CameraConfig

camera = Camera()
camera.start_preview()

preview_config = CameraConfig.for_preview(camera)
capture_config = CameraConfig.for_still(camera)
camera.configure(preview_config)

camera.start()
camera.discard_frames(2)
with TemporaryDirectory() as tmpdir:
    path = f"{tmpdir}/test_full.jpg"
    camera.capture_file(path, config=capture_config).result()
    assert os.path.isfile(path)

camera.close()
