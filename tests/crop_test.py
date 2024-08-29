#!/usr/bin/python3

# Test setting the "preserve_ar" stream configuration flag

import cv2

from picamera2 import Picamera2

picam2 = Picamera2()

for m, l in [(False, False), (False, True), (True, False), (True, True)]:
    cfg = picam2.create_video_configuration(main={"size": (1920, 1080), "format": 'XRGB8888', "preserve_ar": m},
                                            lores={"size": (640, 640), "format": 'XRGB8888', "preserve_ar": l},
                                            display="main")
    picam2.configure(cfg)
    picam2.start(show_preview=True)

    for _ in range(100):
        im = picam2.capture_array("lores")
        cv2.imshow("lores", im)
        cv2.resizeWindow("lores", (640, 640))
        cv2.waitKey(1)

    picam2.stop()
