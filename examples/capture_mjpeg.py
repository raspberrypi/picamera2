#!/usr/bin/python3

from null_preview import *
from jpeg_encoder import *
from picamera2 import *
import time

picam2 = Picamera2()
video_config = picam2.video_configuration(main={"size": (1920, 1080)})
picam2.configure(video_config)

preview = NullPreview(picam2)
encoder = JpegEncoder(q=70)

encoder.output = open('test.mjpeg', 'wb')
picam2.encoder = encoder
picam2.start_encoder()
picam2.start()
time.sleep(10)
picam2.stop()
picam2.stop_encoder()
