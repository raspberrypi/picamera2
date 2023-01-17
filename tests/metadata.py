#!/usr/bin/python3

# Obtain the current camera control values in the image metadata.
from scicamera import Camera, CameraConfig

camera = Camera()
camera.start_preview()

preview_config = CameraConfig.for_preview(camera)
camera.configure(preview_config)

camera.start()
camera.discard_frames(2)
print(camera.capture_metadata().result())
camera.close()
