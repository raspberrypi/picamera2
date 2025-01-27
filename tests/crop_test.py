#!/usr/bin/python3

# Test setting the "preserve_ar" stream configuration flag

import cv2

from picamera2 import Picamera2, Platform

# VC4 platforms do not support different crops for the two outputs.
if Picamera2.platform == Platform.VC4:
    print("SKIPPED (VC4 platform)")
    quit(0)

picam2 = Picamera2()

for m, l in [(False, False), (False, True), (True, False), (True, True)]:
    cfg = picam2.create_video_configuration(main={"size": (1920, 1080), "format": 'XRGB8888', "preserve_ar": m},
                                            lores={"size": (320, 320), "format": 'XRGB8888', "preserve_ar": l},
                                            display="main")
    picam2.configure(cfg)
    picam2.start(show_preview=True)

    for _ in range(50):
        im = picam2.capture_array("lores")
        cv2.imshow("lores", im)
        cv2.waitKey(1)

    picam2.stop()
