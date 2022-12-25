#!/usr/bin/python3
import time

from picamera2 import Picamera2
from picamera2.encoders import Quality
from picamera2.encoders.jpeg_encoder import JpegEncoder

picam2 = Picamera2()
video_config = picam2.create_video_configuration()
picam2.configure(video_config)

encoder = JpegEncoder()

picam2.start_recording(encoder, "low.mjpeg")
time.sleep(1)
picam2.stop_recording()
picam2.close()
