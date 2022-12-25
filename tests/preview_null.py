#!/usr/bin/python3

import time

from picamera2 import Picamera2

camera = Picamera2()
config = camera.create_preview_configuration()
camera.configure(config)

camera.start()
time.sleep(1)
camera.stop()
