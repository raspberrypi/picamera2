#!/usr/bin/python3
import time

from picamera2 import Picamera2
from picamera2.encoders import Quality
from picamera2.encoders.jpeg_encoder import JpegEncoder

camera = Picamera2()
video_config = camera.create_video_configuration()
camera.configure(video_config)

encoder = JpegEncoder()

camera.start_recording(encoder, "low.mjpeg")
time.sleep(1)
camera.stop_recording()
camera.close()
