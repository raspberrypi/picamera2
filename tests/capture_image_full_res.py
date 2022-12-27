#!/usr/bin/python3

# Capture a full resolution image to memory rather than to a file.

import time

from PIL import Image

from picamera2 import Picamera2

camera = Picamera2()
camera.start_preview()
preview_config = camera.create_preview_configuration()
capture_config = camera.create_still_configuration()

camera.configure(preview_config)
camera.start()
time.sleep(2)

image = camera.switch_mode_and_capture_image(capture_config)
assert isinstance(image, Image)

time.sleep(5)

camera.close()
