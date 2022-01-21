#!/usr/bin/python3

# Capture a JPEG while still running in the preview mode. When you
# capture to a file, the return value is the metadata for that image.

from qt_gl_preview import *
from picamera2 import *
import time

picam2 = Picamera2()
preview = QtGlPreview(picam2)

picam2.open_camera()

preview_config = picam2.preview_configuration(raw={"size": picam2.sensor_resolution})
print(preview_config)
picam2.configure(preview_config)

picam2.start()
time.sleep(2)

raw = picam2.capture_array("raw")
print(raw.shape)
print(picam2.stream_configuration("raw"))
