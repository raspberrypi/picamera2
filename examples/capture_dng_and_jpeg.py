#!/usr/bin/python3

# Capture a DNG and a JPEG made from the same raw data.

from picamera2.picamera2 import Picamera2, Preview
import time

picam2 = Picamera2()
picam2.start_preview(Preview.QTGL)

preview_config = picam2.preview_configuration()
capture_config = picam2.still_configuration(raw={}, display=None)
picam2.configure(preview_config)

picam2.start()
time.sleep(2)

r = picam2.switch_mode_capture_request_and_stop(capture_config)
r.save(name="main", filename="full.jpg")
r.save_dng(filename="full.dng")
