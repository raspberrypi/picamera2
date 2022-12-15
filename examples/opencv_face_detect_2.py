#!/usr/bin/python3
import time

import cv2

from picamera2 import MappedArray, Picamera2, Preview

# This version creates a lores YUV stream, extracts the Y channel and runs the face
# detector directly on that. We use the supplied OpenGL accelerated preview window
# and delegate the face box drawing to its callback function, thereby running the
# preview at the full rate with face updates as and when they are ready.

face_detector = cv2.CascadeClassifier(
    "/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml"
)


def draw_faces(request):
    with MappedArray(request, "main") as m:
        for f in faces:
            (x, y, w, h) = [
                c * n // d for c, n, d in zip(f, (w0, h0) * 2, (w1, h1) * 2)
            ]
            cv2.rectangle(m.array, (x, y), (x + w, y + h), (0, 255, 0, 0))


picam2 = Picamera2()
picam2.start_preview(Preview.QTGL)
config = picam2.create_preview_configuration(
    main={"size": (640, 480)}, lores={"size": (320, 240), "format": "YUV420"}
)
picam2.configure(config)

(w0, h0) = picam2.stream_configuration("main")["size"]
(w1, h1) = picam2.stream_configuration("lores")["size"]
s1 = picam2.stream_configuration("lores")["stride"]
faces = []
picam2.post_callback = draw_faces

picam2.start()

start_time = time.monotonic()
# Run for 10 seconds so that we can include this example in the test suite.
while time.monotonic() - start_time < 10:
    buffer = picam2.capture_buffer("lores")
    grey = buffer[: s1 * h1].reshape((h1, s1))
    faces = face_detector.detectMultiScale(grey, 1.1, 3)
