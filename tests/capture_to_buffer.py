#!/usr/bin/python3

import io
import time

from picamera2 import Picamera2

camera = Picamera2()
capture_config = camera.create_still_configuration()
camera.configure(camera.create_preview_configuration())
camera.start()

time.sleep(1)
data = io.BytesIO()
camera.capture_file(data, format="jpeg")
print(data.getbuffer().nbytes)

time.sleep(1)
data = io.BytesIO()
camera.switch_mode_and_capture_file(capture_config, data, format="jpeg")
print(data.getbuffer().nbytes)

camera.close()
