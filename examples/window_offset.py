#!/usr/bin/python3

# Create a preview window at a particular location on the display.

from picamera2 import Picamera2, Preview
import time

picam2 = Picamera2()
picam2.start_preview(Preview.QTGL, x=100, y=200)

preview_config = picam2.preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(2)
