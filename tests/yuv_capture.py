#!/usr/bin/python3
import time

from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder

picam2 = Picamera2()
video_config = picam2.create_video_configuration({"format": "YUV420", "size": (1280, 720)})
picam2.configure(video_config)
encoder = JpegEncoder(q=70)

picam2.start_recording(encoder, 'test.mjpeg')
time.sleep(5)
picam2.stop_recording()

lores = {"size": (640, 480), "format": "YUV420"}
still_config = picam2.create_still_configuration({"format": "YUV420"}, lores=lores)
picam2.configure(still_config)
picam2.start()

time.sleep(2)
picam2.capture_file("test.jpg")

# Also make sure the lores works - a typo had broken this case
picam2.capture_file("lores.jpg", "lores")
