#!/usr/bin/python3
import time

from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder

camera = Picamera2()
video_config = camera.create_video_configuration(main={"size": (1920, 1080)})
camera.configure(video_config)

camera.start_preview()

camera.start()
time.sleep(2)
camera.stop()
camera.close()
