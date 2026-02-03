#!/usr/bin/python3

import cv2

from picamera2 import MappedArray, Picamera2

# Grab images as numpy arrays and leave everything else to OpenCV.

face_detector = cv2.CascadeClassifier("/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml")
cv2.startWindowThread()

picam2 = Picamera2()
main = {"format": 'RGB888', "size": (640, 480)}
lores = {"format": "YUV420", "size": (640, 480)}
picam2.configure(picam2.create_preview_configuration(main, lores=lores))
picam2.start()

while True:
    with picam2.captured_request() as request:
        grey = request.make_array('lores')[:480, :640]

        faces = face_detector.detectMultiScale(grey, 1.1, 5)

        with MappedArray(request, 'main') as m:
            for (x, y, w, h) in faces:
                cv2.rectangle(m.array, (x, y), (x + w, y + h), (0, 255, 0))

            cv2.imshow("Camera", m.array)

    cv2.waitKey(1)
