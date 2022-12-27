#!/usr/bin/python3

# Another (simpler!) way to fix the AEC/AGC and AWB.

import time

from picamera2 import Picamera2

camera = Picamera2()
camera.start_preview()

preview_config = camera.create_preview_configuration()
camera.configure(preview_config)

camera.start()
time.sleep(1)

camera.set_controls({"AwbEnable": 0, "AeEnable": 0})
time.sleep(2)

camera.close()
