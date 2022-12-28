#!/usr/bin/python3
# Capture a JPEG while still running in the preview mode. When you
# capture to a file, the return value is the metadata for that image.

from picamera2 import Picamera2

camera = Picamera2()

preview_config = camera.create_preview_configuration(main={"size": (800, 600)})
camera.configure(preview_config)

camera.start_preview()

camera.start()
camera.discard_frames(2)
metadata = camera.capture_file("test.jpg").result()
print(metadata)

camera.close()
