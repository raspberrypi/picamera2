#!/usr/bin/python3

# Capture multiple representations of a captured frame.

import time

from picamera2 import Picamera2
from picamera2.helpers import Helpers

camera = Picamera2()
camera.start_preview()

preview_config = camera.create_preview_configuration()
capture_config = camera.create_still_configuration(raw={})
camera.configure(preview_config)

camera.start()
time.sleep(2)

buffers, metadata = camera.switch_mode_and_capture_buffers(capture_config, ["main"])

arr = Helpers.make_array(buffers[0], capture_config["main"])
image = Helpers.make_image(buffers[0], capture_config["main"])

camera.close()
