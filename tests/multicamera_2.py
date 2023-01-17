#!/usr/bin/python3

import time

from scicamera import Camera, CameraConfig, CameraInfo

if CameraInfo.n_cameras() <= 1:
    print("SKIPPED (one camera)")
    quit()

camera1 = Camera(0)
config1 = CameraConfig.for_preview(camera1)
camera1.configure(config1)
camera1.start_preview()
camera1.start()

time.sleep(2)
camera1.capture_file("testa.jpg").result()

camera2 = Camera(1)
config2 = CameraConfig.for_preview(camera2)
camera2.configure(config2)
camera2.start()

time.sleep(2)
camera1.stop()

camera2.capture_file("testb.jpg").result()

camera2.stop()
camera1.close()
camera2.close()
