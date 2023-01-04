#!/usr/bin/python3
from picamera2 import CameraConfig, Picamera2


def takephoto(cam):
    camera = Picamera2(camera_num=cam)
    capture_config = CameraConfig.for_still(camera)
    camera.start()
    camera.switch_mode_and_capture_file(capture_config, f"cam{cam}.jpg")
    camera.stop()
    camera.close()


for cam in range(4):
    takephoto(cam)

# Or
for cam in range(4):
    camera = Picamera2(camera_num=cam)
    capture_config = CameraConfig.for_still(camera)
    camera.start()
    camera.capture_file(f"cam{cam}.jpg", config=capture_config)
    camera.stop()
    camera.close()
