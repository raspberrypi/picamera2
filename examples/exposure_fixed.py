#!/usr/bin/python3

# Start camera with fixed exposure and gain.

from picamera2 import Picamera2, Preview
import time

picam2 = Picamera2()
picam2.start_preview(Preview.QTGL)

preview_config = picam2.preview_configuration()
picam2.configure(preview_config)

picam2.start({"ExposureTime": 10000, "AnalogueGain": 1.0})
time.sleep(5)
