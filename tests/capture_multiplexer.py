#!/usr/bin/python3

import picamera2


def takephoto(cam):
    camera = picamera2.Picamera2(camera_num=cam)
    capture_config = camera.create_still_configuration()
    camera.start()
    camera.switch_mode_and_capture_file(capture_config, f"cam{cam}.jpg")
    camera.stop()
    camera.close()


for cam in range(4):
    takephoto(cam)

# Or
for cam in range(4):
    camera = picamera2.Picamera2(camera_num=cam)
    capture_config = camera.create_still_configuration()
    camera.start()
    camera.switch_mode_and_capture_file(capture_config, f"cam{cam}.jpg")
    camera.stop()
    camera.close()
