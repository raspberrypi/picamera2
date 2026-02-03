#!/usr/bin/python3

# This is the most high level way to capture images and save them. Howwever,
# the API gives you less control over the camera system so we would recommend
# it only to folks with the simplest use-cases.

from picamera2 import Picamera2

picam2 = Picamera2()

# Capture one image with the default configurations.
picam2.start_and_capture_file("test.jpg")

# Capture 3 images. Use a 0.5 second delay after the first image.
picam2.start_and_capture_files("test{:d}.jpg", num_files=3, delay=0.5)  # noqa
