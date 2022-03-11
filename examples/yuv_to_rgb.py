#!/usr/bin/python3

from picamera2.previews.null_preview import *
from picamera2.picamera2 import *
from picamera2.converters import *
import cv2

cv2.startWindowThread()

picam2 = Picamera2()
picam2.start_preview(NullPreview())
config = picam2.preview_configuration(lores={"size": (640, 480)})
picam2.configure(config)
picam2.start()

while True:
    buffer = picam2.capture_buffer("lores")
    rgb = YUV420_to_RGB(buffer, (640, 480))
    cv2.imshow("Camera", rgb)

