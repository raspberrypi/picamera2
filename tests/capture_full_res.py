#!/usr/bin/python3
# Capture a JPEG while still running in the preview mode.
from scicamera import Camera, CameraConfig
from scicamera.configuration import CameraConfig

camera = Camera()
camera.start_preview()

preview_config = CameraConfig.for_preview(camera)
capture_config = CameraConfig.for_still(camera)
camera.configure(preview_config)

camera.start()
camera.discard_frames(2)
camera.capture_file("test_full.jpg", config=capture_config).result()
camera.close()
