#!/usr/bin/python3

# Capture a PNG while still running in the preview mode.

from picamera2.picamera2 import *
import time

picam2 = Picamera2()
picam2.start_preview('QT')

preview_config = picam2.preview_configuration(main={"size": (800, 600)})
picam2.configure(preview_config)

picam2.start_camera()
time.sleep(2)

picam2.capture_file("test.png")

print("Sleeping for 10 seconds...")
time.sleep(10)
picam2.close_camera()
