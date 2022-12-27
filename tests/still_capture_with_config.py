#!/usr/bin/python3

# Use the configuration structure method to do a full res capture.

import time

from picamera2 import Picamera2

camera = Picamera2()

# We don't really need to change anyhting, but let's mess around just as a test.
camera.preview_configuration.size = (800, 600)
camera.preview_configuration.format = "YUV420"
camera.still_configuration.size = (1600, 1200)
camera.still_configuration.enable_raw()
camera.still_configuration.raw.size = camera.sensor_resolution

camera.start("preview")
time.sleep(2)

camera.switch_mode_and_capture_file("still", "test_full.jpg")
