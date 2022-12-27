#!/usr/bin/python3

# Example of setting controls using the "direct" attribute method.

import time

from picamera2 import Picamera2
from picamera2.controls import Controls

camera = Picamera2()
camera.start_preview()

preview_config = camera.create_preview_configuration()
camera.configure(preview_config)

camera.start()
time.sleep(1)

with camera.controls as ctrl:
    ctrl.AnalogueGain = 6.0
    ctrl.ExposureTime = 60000

time.sleep(2)

ctrls = Controls(camera)
ctrls.AnalogueGain = 1.0
ctrls.ExposureTime = 10000
camera.set_controls(ctrls)

time.sleep(2)
camera.close()
