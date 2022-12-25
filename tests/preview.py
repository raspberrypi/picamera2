#!/usr/bin/python3

# Normally the QtGlPreview implementation is recommended as it benefits
# from GPU hardware acceleration.

import time

from picamera2 import Picamera2, Preview

camera = Picamera2()
camera.start_preview(Preview.NULL)

preview_config = camera.create_preview_configuration()
camera.configure(preview_config)

camera.start()
time.sleep(5)
