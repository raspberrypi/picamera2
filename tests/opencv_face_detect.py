#!/usr/bin/python3

import cv2

from picamera2 import Picamera2

# Grab images as numpy arrays and leave everything else to OpenCV.

face_detector = cv2.CascadeClassifier(
    "/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml"
)
cv2.startWindowThread()

picam2 = Picamera2()
picam2.configure(
    picam2.create_preview_configuration(main={"format": "XRGB8888", "size": (640, 480)})
)
picam2.start()

while True:
    im = picam2.capture_array()

    grey = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    faces = face_detector.detectMultiScale(grey, 1.1, 5)

    for (x, y, w, h) in faces:
        cv2.rectangle(im, (x, y), (x + w, y + h), (0, 255, 0))

    cv2.imshow("Camera", im)
