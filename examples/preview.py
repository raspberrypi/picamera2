#!/usr/bin/python3

# Normally the QtGlPreview implementation is recommended as it benefits
# from GPU hardware acceleration.

from picamera2.picamera2 import *
import time

picam2 = Picamera2()
picam2.start_preview(Preview.QTGL)

preview_config = picam2.preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(5)
