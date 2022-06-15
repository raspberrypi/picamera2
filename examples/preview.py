#!/usr/bin/python3

# Normally the QtGlPreview implementation is recommended as it benefits
# from GPU hardware acceleration.

import time

from picamera2 import Picamera2, Preview

picam2 = Picamera2()
picam2.start_preview(Preview.QTGL)

preview_config = picam2.create_preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(5)
