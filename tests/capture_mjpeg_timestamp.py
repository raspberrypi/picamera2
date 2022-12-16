#!/usr/bin/python3
import time

from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder

picam2 = Picamera2()
video_config = picam2.create_video_configuration(main={"size": (1920, 1080)})
picam2.configure(video_config)

picam2.start_preview()
encoder = JpegEncoder(q=70)

picam2.start_recording(encoder, "test.mjpeg", pts="timestamp.txt")
time.sleep(10)
picam2.stop_recording()
picam2.close()
