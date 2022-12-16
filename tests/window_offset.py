#!/usr/bin/python3

# Create a preview window at a particular location on the display.

import time

from picamera2 import Picamera2, Preview

picam2 = Picamera2()
picam2.start_preview(Preview.NULL, x=100, y=200)

preview_config = picam2.create_preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(2)
