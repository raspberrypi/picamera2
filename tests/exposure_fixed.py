#!/usr/bin/python3
# Start camera with fixed exposure and gain.
from picamera2 import Picamera2

camera = Picamera2()
camera.start_preview()
controls = {"ExposureTime": 10000, "AnalogueGain": 1.0}
preview_config = camera.create_preview_configuration(controls=controls)
camera.configure(preview_config)

camera.start()
camera.discard_frames(2)
camera.close()
