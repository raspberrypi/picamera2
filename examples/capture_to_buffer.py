#!/usr/bin/python3

from picamera2 import Picamera2
import io
import time

picam2 = Picamera2()
capture_config = picam2.still_configuration()
picam2.configure(picam2.preview_configuration())
picam2.start()

time.sleep(1)
data = io.BytesIO()
picam2.capture_file(data, format='jpeg')
print(data.getbuffer().nbytes)

time.sleep(1)
data = io.BytesIO()
picam2.switch_mode_and_capture_file(capture_config, data, format='jpeg')
print(data.getbuffer().nbytes)
