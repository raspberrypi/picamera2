#!/usr/bin/python3

# This example adds multiple exposures together to create a much longer exposure
# image. It does this by disabling the gamma transform (which is non-linear and
# prevents us from adding the images straightforwardly), but then we must recreate
# it and apply it ourselves at the end.

import cv2
import numpy as np
from picamera2 import Picamera2


exposure_time = 60000  # put your own numbers here
num_frames = 6

# We must tweak the tuning to disable the non-linear gamma transform. Load the
# tuning file for the sensor that you have attached.
tuning = Picamera2.load_tuning_file("imx477.json")
contrast_algo = Picamera2.find_tuning_algo(tuning, "rpi.contrast")
gamma_curve = contrast_algo["gamma_curve"]
contrast_algo["ce_enable"] = 0
contrast_algo["gamma_curve"] = [0, 0, 65535, 65535]

# Create a gamma lookup table to apply at the end.
gamma_x = np.array(gamma_curve[::2], dtype=float) * 255 / 65535
gamma_y = np.array(gamma_curve[1::2], dtype=float) * 255 / 65535
gamma_lut = np.interp(range(num_frames * 255 + 1), gamma_x, gamma_y, right=255).astype(np.uint8)

picam2 = Picamera2(tuning=tuning)
config = picam2.create_still_configuration({"format": "RGB888"}, buffer_count=2)
picam2.configure(config)
images = []
picam2.set_controls({"ExposureTime": exposure_time // num_frames, "AnalogueGain": 1.0})
picam2.start()

for i in range(num_frames):
    images.append(picam2.capture_array())

# Add the images up, apply the gamma transform and we're done.
accumulated = images.pop(0).astype(np.uint16)
for image in images:
    accumulated += image
accumulated = gamma_lut[accumulated]

cv2.imwrite("accumulated.jpg", accumulated)
