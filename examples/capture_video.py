#!/usr/bin/python3

from null_preview import *
from h264_encoder import *
from picamera2 import *
import time
import os

picam2 = Picamera2()
picam2.open_camera()

video_config = picam2.video_configuration()
picam2.configure(video_config)

preview = NullPreview(picam2)
encoder = H264Encoder(10000000)

encoder.output = open('test.h264', 'wb')
picam2.encoder = encoder
picam2.start_encoder()
picam2.start({"FrameDurationLimits": (33333, 33333)})
time.sleep(10)
picam2.stop()
picam2.stop_encoder()
