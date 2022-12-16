#!/usr/bin/python3

# Start camera with fixed exposure and gain.

import time

from picamera2 import Picamera2, Preview

picam2 = Picamera2()
picam2.start_preview(Preview.NULL)
controls = {"ExposureTime": 10000, "AnalogueGain": 1.0}
preview_config = picam2.create_preview_configuration(controls=controls)
picam2.configure(preview_config)

picam2.start()
time.sleep(5)
picam2.close()
