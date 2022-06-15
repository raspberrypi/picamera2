#!/usr/bin/python3

# Capture a DNG and a JPEG made from the same raw data.

import time

from picamera2 import Picamera2, Preview

picam2 = Picamera2()
picam2.start_preview(Preview.QTGL)

preview_config = picam2.create_preview_configuration()
capture_config = picam2.create_still_configuration(raw={}, display=None)
picam2.configure(preview_config)

picam2.start()
time.sleep(2)

r = picam2.switch_mode_capture_request_and_stop(capture_config)
r.save("main", "full.jpg")
r.save_dng("full.dng")
