#!/bin/python3

from picamera2 import Picamera2
from picamera2.devices.imx708 import IMX708

camera_info = Picamera2.global_camera_info()
camera_num = next((c['Num'] for c in camera_info if c['Model'] == 'imx708'), None)

if camera_num is not None:
    with IMX708(camera_num) as cam:
        cam.set_sensor_hdr_mode(True)
        picam2 = Picamera2(camera_num)
        if len(picam2.sensor_modes) != 1:
            print("ERROR: We should only report 1 sensor HDR mode")
        picam2.close()

        cam.set_sensor_hdr_mode(False)
        picam2 = Picamera2(camera_num)
        if len(picam2.sensor_modes) <= 1:
            print("ERROR: We should report > 1 sensor non-HDR modes")
        picam2.close()

    cam = IMX708(camera_num)
    cam.set_sensor_hdr_mode(True)
    picam2 = Picamera2(camera_num)
    if len(picam2.sensor_modes) != 1:
        print("ERROR: We should only report 1 sensor HDR mode")
    picam2.close()

    # Be sure to leave us in the HDR off state!
    cam = IMX708(camera_num)
    cam.set_sensor_hdr_mode(False)
    picam2 = Picamera2(camera_num)
    if len(picam2.sensor_modes) <= 1:
        print("ERROR: We should only report 1 sensor HDR mode")
    picam2.close()
