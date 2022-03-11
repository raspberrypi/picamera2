#!/usr/bin/python3

# Obtain the current camera control values in the image metadata.

from picamera2.previews.qt_gl_preview import *
from picamera2.picamera2 import *
import time

picam2 = Picamera2()
picam2.start_preview(QtGlPreview())

preview_config = picam2.preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(2)

print(picam2.capture_metadata())
