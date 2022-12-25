#!/usr/bin/python3

# For use from the login console, when not running X Windows.

import time

from picamera2 import Picamera2, Preview

camera = Picamera2()
camera.start_preview(Preview.NULL, x=100, y=100, width=640, height=480)

preview_config = camera.create_preview_configuration({"size": (640, 360)})
camera.configure(preview_config)

camera.start()
time.sleep(5)
