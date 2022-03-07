#!/usr/bin/python3

"""
In this example, a "with" statement is used to automatically open your camera
and then close it after all the operations within the "with" statement
are completed.
"""

from picamera2 import *
from null_preview import *

camera_num = 0  # Let's choose the camera at index 0.
verbose = 1  # Let's also print informative messages to the console.

with Picamera2(camera_num, verbose) as picam2:
    config = picam2.still_configuration()
    picam2.configure(config)
    preview = NullPreview(picam2) # Don't preview the camera.
    picam2.start()
    np_array = picam2.capture_array()
    print(np_array)
    picam2.capture_file("context_demo.png")
