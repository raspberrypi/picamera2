#!/usr/bin/python3

import time

from picamera2 import CameraInfo, Picamera2

if CameraInfo.n_cameras() <= 1:
    print("SKIPPED (one camera)")
    quit()

camera1 = Picamera2(0)
camera1.configure(camera1.create_preview_configuration())
camera1.start_preview()

camera2 = Picamera2(1)
camera2.configure(camera2.create_preview_configuration())
camera2.start_preview()

camera1.start()
camera2.start()

time.sleep(2)
print(camera1.capture_metadata())
time.sleep(2)
print(camera2.capture_metadata())
camera1.capture_file("testa.jpg")
camera2.capture_file("testb.jpg")

camera1.stop()
camera2.stop()

camera1.close()
camera2.close()
