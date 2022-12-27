#!/usr/bin/python3

# Capture a JPEG while still running in the preview mode.

import time

from picamera2 import Picamera2

camera = Picamera2()
camera.start_preview()

preview_config = camera.create_preview_configuration()
capture_config = camera.create_still_configuration()
camera.configure(preview_config)

camera.start()
time.sleep(2)

camera.switch_mode_and_capture_file(capture_config, "test_full.jpg")

camera.close()
