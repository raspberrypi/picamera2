#!/usr/bin/python3

# Use the configuration structure method to do a full res capture.

import time

from picamera2 import Picamera2

camera = Picamera2()

# We don't really need to change anything, but let's mess around just as a test.
camera.video_configuration.size = (800, 480)
camera.video_configuration.format = "YUV420"

camera.start()
time.sleep(2)
camera.stop()
