#!/usr/bin/python3
# Capture a PNG while still running in the preview mode.

from scicamera import Camera, CameraConfig

camera = Camera()
camera.start_preview()

preview_config = CameraConfig.for_preview(camera, main={"size": (800, 600)})
camera.configure(preview_config)

camera.start()
camera.discard_frames(2)
camera.capture_file("test.png").result()
camera.close()
