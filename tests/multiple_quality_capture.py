#!/usr/bin/python3
import time

from picamera2 import Picamera2

camera = Picamera2()
video_config = camera.create_video_configuration()
camera.configure(video_config)

camera.start()
time.sleep(1)
camera.stop()
camera.close()
