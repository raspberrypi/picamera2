#!/usr/bin/python3

import time

from picamera2 import CameraInfo, Picamera2

if CameraInfo.n_cameras() <= 1:
    print("SKIPPED (one camera)")
    quit()

camera1 = Picamera2(0)
camera1.configure(camera1.create_preview_configuration())
camera1.start_preview()
camera1.start()

time.sleep(2)
camera1.capture_file("testa.jpg").result()

camera2 = Picamera2(1)
camera2.configure(camera2.create_preview_configuration())
camera2.start()

time.sleep(2)
camera1.stop()

camera2.capture_file("testb.jpg").result()

camera2.stop()
camera1.close()
camera2.close()
