#!/usr/bin/python3

# Start camera with fixed exposure and gain.

from qt_gl_preview import *
from picamera2 import *
import time

picam2 = Picamera2()
preview = QtGlPreview(picam2)

picam2.open_camera()

preview_config = picam2.preview_configuration()
picam2.configure(preview_config)

picam2.start({"ExposureTime": 10000, "AnalogueGain": 1.0})
time.sleep(5)
