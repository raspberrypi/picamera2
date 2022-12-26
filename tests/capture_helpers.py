#!/usr/bin/python3

# Capture multiple representations of a captured frame.

import time

from picamera2 import Picamera2
from picamera2.helpers import Helpers

picam2 = Picamera2()
picam2.start_preview()

preview_config = picam2.create_preview_configuration()
capture_config = picam2.create_still_configuration(raw={})
picam2.configure(preview_config)

picam2.start()
time.sleep(2)

buffers, metadata = picam2.switch_mode_and_capture_buffers(capture_config, ["main"])

arr = Helpers.make_array(buffers[0], capture_config["main"])
image = Helpers.make_image(buffers[0], capture_config["main"])

picam2.close()
