#!/usr/bin/python3

import cv2

from picamera2.picamera2 import *

# This version creates a lores YUV stream, extracts the Y channel and runs the face
# detector directly on that. We use the supplied OpenGL accelerated preview window
# and delegate the face box drawing to its callback function, thereby running the
# preview at the full rate with face updates as and when they are ready.

face_detector = cv2.CascadeClassifier("/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml")


def draw_faces(request):
    stream = request.picam2.stream_map["main"]
    fb = request.request.buffers[stream]
    with fb.mmap(0) as b:
        im = np.array(b, copy=False, dtype=np.uint8).reshape((h0, w0, 4))
        for f in faces:
            (x, y, w, h) = [c * n // d for c, n, d in zip(f, (w0, h0) * 2, (w1, h1) * 2)]
            cv2.rectangle(im, (x, y), (x + w, y + h), (0, 255, 0, 0))
        del im


picam2 = Picamera2()
picam2.start_preview(Preview.QTGL)
config = picam2.preview_configuration(main={"size": (640, 480)},
                                      lores={"size": (320, 240), "format": "YUV420"})
picam2.configure(config)

(w0, h0) = picam2.stream_configuration("main")["size"]
(w1, h1) = picam2.stream_configuration("lores")["size"]
s1 = picam2.stream_configuration("lores")["stride"]
faces = []
picam2.request_callback = draw_faces

picam2.start()

while True:
    buffer = picam2.capture_buffer("lores")
    grey = buffer[:s1 * h1].reshape((h1, s1))
    faces = face_detector.detectMultiScale(grey, 1.1, 3)
