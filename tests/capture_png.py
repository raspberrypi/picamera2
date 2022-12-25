#!/usr/bin/python3

# Capture a PNG while still running in the preview mode.

import time

from picamera2 import Picamera2

picam2 = Picamera2()
picam2.start_preview()

preview_config = picam2.create_preview_configuration(main={"size": (800, 600)})
picam2.configure(preview_config)

picam2.start()
time.sleep(2)

picam2.capture_file("test.png")
picam2.close()
