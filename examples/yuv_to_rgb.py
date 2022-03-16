#!/usr/bin/python3

from picamera2.picamera2 import *
from picamera2.converters import *
import cv2

cv2.startWindowThread()

picam2 = Picamera2()
picam2.start_preview()
config = picam2.preview_configuration(lores={"size": (640, 480)})
picam2.configure(config)
picam2.start()

start_time = time.monotonic()
# Run for 10 seconds so that we can include this example in the test suite.
while time.monotonic() - start_time < 10:
    buffer = picam2.capture_buffer("lores")
    rgb = YUV420_to_RGB(buffer, (640, 480))
    cv2.imshow("Camera", rgb)
