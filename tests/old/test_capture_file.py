#!/usr/bin/python3
# Capture a JPEG while still running in the preview mode. When you
# capture to a file, the return value is the metadata for that image.

import os
from tempfile import TemporaryDirectory

from scicamera import Camera, CameraConfig

camera = Camera()

preview_config = CameraConfig.for_preview(camera, main={"size": (800, 600)})
camera.configure(preview_config)

camera.start_preview()

camera.start()
camera.discard_frames(2)
with TemporaryDirectory() as tmpdir:
    for extension in ["jpg", "png"]:
        filepath = f"{tmpdir}/test.{extension}"
        metadata = camera.capture_file(filepath).result()
        assert os.path.isfile(filepath)

print(metadata)

camera.close()
