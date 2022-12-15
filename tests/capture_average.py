#!/usr/bin/python3

"""Example comparing capturing a single photo vs capturing multiple photos and averaging to try to reduce noise"""

import time

import numpy as np
from PIL import Image

from picamera2 import Picamera2, Preview

picam2 = Picamera2()
picam2.start_preview(Preview.NULL)
capture_config = picam2.create_still_configuration()
picam2.configure(capture_config)

picam2.start()
time.sleep(2)

with picam2.controls as ctrl:
    ctrl.AnalogueGain = 1.0
    ctrl.ExposureTime = 400000
time.sleep(2)

imgs = 20  # Capture 20 images to average
sumv = None
for i in range(imgs):
    if sumv is None:
        sumv = np.longdouble(picam2.capture_array())
        img = Image.fromarray(np.uint8(sumv))
        img.save("original.tif")
    else:
        sumv += np.longdouble(picam2.capture_array())

img = Image.fromarray(np.uint8(sumv / imgs))
img.save("averaged.tif")
