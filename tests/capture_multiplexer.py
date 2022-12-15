#!/usr/bin/python3

import picamera2


def takephoto(cam):
    picam2 = picamera2.Picamera2(camera_num=cam)
    capture_config = picam2.create_still_configuration()
    picam2.start()
    picam2.switch_mode_and_capture_file(capture_config, f"cam{cam}.jpg")
    picam2.stop()
    picam2.close()


for cam in range(4):
    takephoto(cam)

# Or
for cam in range(4):
    picam2 = picamera2.Picamera2(camera_num=cam)
    capture_config = picam2.create_still_configuration()
    picam2.start()
    picam2.switch_mode_and_capture_file(capture_config, f"cam{cam}.jpg")
    picam2.stop()
    picam2.close()
