#!/usr/bin/python3

# Capture a PNG while still running in the preview mode.

import time

from picamera2 import Picamera2

camera = Picamera2()
camera.start_preview()

preview_config = camera.create_preview_configuration(main={"size": (800, 600)})
camera.configure(preview_config)

camera.start()
time.sleep(2)

camera.capture_file("test.png")
camera.close()
