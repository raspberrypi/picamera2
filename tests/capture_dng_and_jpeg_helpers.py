#!/usr/bin/python3

# Capture a DNG and a JPEG made from the same raw data.

import time

from picamera2 import Picamera2

picam2 = Picamera2()
picam2.start_preview()

preview_config = picam2.create_preview_configuration()
capture_config = picam2.create_still_configuration(raw={})
picam2.configure(preview_config)

picam2.start()
time.sleep(2)

buffers, metadata = picam2.switch_mode_and_capture_buffers(
    capture_config, ["main", "raw"]
)
picam2.helpers.save(
    picam2.helpers.make_image(buffers[0], capture_config["main"]), metadata, "full.jpg"
)
picam2.helpers.save(buffers[1], metadata, "full.jpeg")
