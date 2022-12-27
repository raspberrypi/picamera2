#!/usr/bin/python3

# Capture a DNG and a JPEG made from the same raw data.

import time

from picamera2 import Picamera2

camera = Picamera2()
camera.start_preview()

preview_config = camera.create_preview_configuration()
capture_config = camera.create_still_configuration(raw={}, display=None)
camera.configure(preview_config)

camera.start()
time.sleep(2)

r = camera.switch_mode_capture_request_and_stop(capture_config)
r.save("main", "full.jpg")

camera.close()
