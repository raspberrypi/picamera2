#!/usr/bin/python3

# For use from the login console, when not running X Windows.

from picamera2.picamera2 import Picamera2, Preview
import time

picam2 = Picamera2()
picam2.start_preview(Preview.DRM, x=100, y=100, width=640, height=480)

preview_config = picam2.preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(5)
