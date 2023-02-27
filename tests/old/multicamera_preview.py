#!/usr/bin/python3

import time

from scicamera import Camera, CameraConfig

camera1 = Camera(0)
camera1.configure(CameraConfig.for_preview(camera1))
camera1.start_preview()

camera2 = Camera(1)
camera2.configure(CameraConfig.for_preview(camera2))
camera2.start_preview()

camera1.start()
camera2.start()
time.sleep(2)
camera1.stop_preview()
camera2.stop_preview()

time.sleep(2)

camera1.start_preview()
camera2.start_preview()

time.sleep(2)
camera1.close()
camera2.close()
