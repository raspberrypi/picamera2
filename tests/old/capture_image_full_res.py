#!/usr/bin/python3
# Capture a full resolution image to memory rather than to a file.
from PIL import Image

from scicamera import Camera, CameraConfig
from scicamera.testing import mature_after_frames_or_timeout

camera = Camera()
camera.start_preview()
preview_config = CameraConfig.for_preview(camera)
capture_config = CameraConfig.for_still(camera)

camera.configure(preview_config)
camera.start()
mature_after_frames_or_timeout(camera, 5).result()

image = camera.capture_image(config=capture_config).result()
assert isinstance(image, Image.Image)

mature_after_frames_or_timeout(camera, 5).result()

camera.close()
