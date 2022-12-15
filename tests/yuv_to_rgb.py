#!/usr/bin/python3

import cv2

from picamera2 import Picamera2

cv2.startWindowThread()

picam2 = Picamera2()
config = picam2.create_preview_configuration(lores={"size": (640, 480)})
picam2.configure(config)
picam2.start()

while True:
    yuv420 = picam2.capture_array("lores")
    rgb = cv2.cvtColor(yuv420, cv2.COLOR_YUV420p2RGB)
    cv2.imshow("Camera", rgb)
