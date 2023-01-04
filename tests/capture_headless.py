#!/usr/bin/python3
from picamera2 import CameraConfig, Picamera2

camera = Picamera2()
config = CameraConfig.for_still(camera)
camera.configure(config)

camera.start()

np_array = camera.capture_array()
camera.discard_frames(2)
camera.capture_file("demo.jpg").result()
camera.stop()
camera.close()
