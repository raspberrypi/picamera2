#!/usr/bin/python3

import time

from picamera2 import Picamera2, Preview

camera = Picamera2()
config = camera.create_preview_configuration()
camera.configure(config)

# In fact, picam2.start() would do this anyway for us:
camera.start_preview(Preview.NULL)

camera.start()
time.sleep(1)
camera.stop()
