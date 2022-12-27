#!/usr/bin/python3

# Capture a DNG and a JPEG made from the same raw data.

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

buffers, metadata = camera.switch_mode_and_capture_buffers(
    capture_config, ["main", "raw"]
)

Helpers.save(
    camera, Helpers.make_image(buffers[0], capture_config["main"]), metadata, "full.jpg"
)
Helpers.save(camera, buffers[1], metadata, "full.jpeg")
