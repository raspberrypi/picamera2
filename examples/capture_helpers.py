#!/usr/bin/python3

# Capture multiple representations of a captured frame.

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

buffers, metadata = picam2.switch_mode(capture_config, ["main"])
request = picam2.capture_request()
request_copy = request.copy()
request.release()

arr = request_copy.make_array("main")
image = request_copy.make_image("main")
