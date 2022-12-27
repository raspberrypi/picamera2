#!/usr/bin/python3

# Start camera with fixed exposure and gain.

import time

from picamera2 import Picamera2

camera = Picamera2()
camera.start_preview()
controls = {"ExposureTime": 10000, "AnalogueGain": 1.0}
preview_config = camera.create_preview_configuration(controls=controls)
camera.configure(preview_config)

camera.start()
time.sleep(5)
camera.close()
