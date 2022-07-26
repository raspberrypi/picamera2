#!/usr/bin/python3

# Example of setting controls using the "direct" attribute method.

from picamera2 import Picamera2, Preview
import time

from picamera2.controls import Controls

picam2 = Picamera2()
picam2.start_preview(Preview.QTGL)

preview_config = picam2.create_preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(1)

with picam2.controls as ctrl:
    ctrl.AnalogueGain = 6.0
    ctrl.ExposureTime = 60000

time.sleep(2)

ctrls = Controls(picam2)
ctrls.AnalogueGain = 1.0
ctrls.ExposureTime = 10000
picam2.set_controls(ctrls)

time.sleep(2)
