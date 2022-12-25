#!/usr/bin/python3

# How to do digital zoom using the "ScalerCrop" control.

from picamera2 import Picamera2

picam2 = Picamera2()
picam2.start_preview()

preview_config = picam2.create_preview_configuration()
picam2.configure(preview_config)

picam2.start()

size = picam2.capture_metadata()["ScalerCrop"][2:]

for _ in range(20):
    # This syncs us to the arrival of a new camera frame:
    picam2.capture_metadata()

    size = [int(s * 0.95) for s in size]
    offset = [(r - s) // 2 for r, s in zip(picam2.sensor_resolution, size)]
    picam2.set_controls({"ScalerCrop": offset + size})

picam2.stop()
picam2.close()
