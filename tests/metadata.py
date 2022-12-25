#!/usr/bin/python3

# Obtain the current camera control values in the image metadata.

import time

from picamera2 import Picamera2

picam2 = Picamera2()
picam2.start_preview()

preview_config = picam2.create_preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(2)

print(picam2.capture_metadata())
picam2.close()
