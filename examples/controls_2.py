#!/usr/bin/python3

# Another (simpler!) way to fix the AEC/AGC and AWB.

from picamera2.picamera2 import *
import time

picam2 = Picamera2()
picam2.start_preview(Preview.QTGL)

preview_config = picam2.preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(1)

picam2.set_controls({"AwbEnable": 0, "AeEnable": 0})
time.sleep(5)
