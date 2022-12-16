#!/usr/bin/python3

# Capture a full resolution image to memory rather than to a file.

import time

from picamera2 import Picamera2, Preview

picam2 = Picamera2()
picam2.start_preview(Preview.NULL)
preview_config = picam2.create_preview_configuration()
capture_config = picam2.create_still_configuration()

picam2.configure(preview_config)
picam2.start()
time.sleep(2)

image = picam2.switch_mode_and_capture_image(capture_config)
image.show()


time.sleep(5)

picam2.close()
