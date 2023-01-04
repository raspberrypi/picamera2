#!/usr/bin/python3
# Example of setting controls using the "direct" attribute method.
from picamera2 import CameraConfig, Picamera2
from picamera2.controls import Controls

camera = Picamera2()
camera.start_preview()

preview_config = CameraConfig.for_preview(camera)
camera.configure(preview_config)

camera.start()
camera.discard_frames(2)

with camera.controls as ctrl:
    ctrl.AnalogueGain = 6.0
    ctrl.ExposureTime = 60000

camera.discard_frames(2)

ctrls = Controls(camera)
ctrls.AnalogueGain = 1.0
ctrls.ExposureTime = 10000
camera.set_controls(ctrls)
camera.discard_frames(2).result()
camera.close()
