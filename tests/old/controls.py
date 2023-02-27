#!/usr/bin/python3

# Example of setting controls. Here, after one second, we fix the AGC/AEC
# to the values it has reached whereafter it will no longer change.
from pprint import pprint

from scicamera import Camera, CameraConfig
from scicamera.testing import requires_controls

camera = Camera()
requires_controls(camera, ("ExposureTime", "AnalogueGain", "ColourGains"))

camera.start_preview()

preview_config = CameraConfig.for_preview(camera)
camera.configure(preview_config)
available_controls = camera.controls.available_control_names()

camera.start()
camera.discard_frames(2)
metadata = camera.capture_metadata().result()
pprint(metadata)
controls = {
    c: metadata[c]
    for c in ["ExposureTime", "AnalogueGain", "ColourGains"]
    if c in available_controls
}
print(controls)

camera.set_controls(controls)
camera.discard_frames(2)

camera.close()
