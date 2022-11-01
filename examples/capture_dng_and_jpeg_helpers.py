#!/usr/bin/python3

# Capture a DNG and a JPEG made from the same raw data.

from picamera2 import Picamera2, Preview
from picamera2.request import RequestCopy
import time

picam2 = Picamera2()
picam2.start_preview(Preview.QTGL)

preview_config = picam2.create_preview_configuration()
capture_config = picam2.create_still_configuration(raw={})
picam2.configure(preview_config)

picam2.start()
time.sleep(2)

buffers, metadata = picam2.switch_mode_and_capture_buffers(capture_config, ["main", "raw"])

request_like = RequestCopy(buffers, metadata, capture_config)
request_like.save("full.jpg")
request_like.save_dng("full.dng")
