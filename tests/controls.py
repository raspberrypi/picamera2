#!/usr/bin/python3

# Example of setting controls. Here, after one second, we fix the AGC/AEC
# to the values it has reached whereafter it will no longer change.

import time

from picamera2 import Picamera2

camera = Picamera2()
camera.start_preview()

preview_config = camera.create_preview_configuration()
camera.configure(preview_config)

camera.start()
time.sleep(1)

metadata = camera.capture_metadata()
controls = {c: metadata[c] for c in ["ExposureTime", "AnalogueGain", "ColourGains"]}
print(controls)

camera.set_controls(controls)
time.sleep(5)

camera.close()
