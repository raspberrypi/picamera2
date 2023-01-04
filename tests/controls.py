#!/usr/bin/python3

# Example of setting controls. Here, after one second, we fix the AGC/AEC
# to the values it has reached whereafter it will no longer change.
from picamera2 import CameraConfig, Picamera2

camera = Picamera2()
camera.start_preview()

preview_config = CameraConfig.for_preview(camera)
camera.configure(preview_config)

camera.start()
camera.discard_frames(2)
metadata = camera.capture_metadata().result()
controls = {c: metadata[c] for c in ["ExposureTime", "AnalogueGain", "ColourGains"]}
print(controls)

camera.set_controls(controls)
camera.discard_frames(2)

camera.close()
