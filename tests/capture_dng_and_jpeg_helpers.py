#!/usr/bin/python3
# Capture a DNG and a JPEG made from the same raw data.
from scicamera import Camera, CameraConfig
from scicamera.configuration import CameraConfig
from scicamera.testing import mature_after_frames_or_timeout

camera = Camera()
camera.start_preview()

preview_config = CameraConfig.for_preview(camera)
capture_config = CameraConfig.for_still(camera, raw={})
camera.configure(preview_config)

camera.start()
mature_after_frames_or_timeout(camera, 2).result()
camera.switch_mode(capture_config).result()
buffers, metadata = camera.capture_buffers_and_metadata(["main", "raw"]).result()

camera.stop()
camera.close()
