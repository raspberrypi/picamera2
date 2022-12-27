#!/usr/bin/python3
import time

from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder

camera = Picamera2()
video_config = camera.create_video_configuration(main={"size": (1920, 1080)})
camera.configure(video_config)

camera.start_preview()
encoder = JpegEncoder(q=70)

camera.start_recording(encoder, "test.mjpeg", pts="timestamp.txt")
time.sleep(2)
camera.stop_recording()
camera.close()
