#!/usr/bin/python3

# Example using PyavOutput to record to an mp4 file.

import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import PyavOutput

picam2 = Picamera2()
config = picam2.create_video_configuration({'size': (1280, 720), 'format': 'YUV420'})
picam2.configure(config)

encoder = H264Encoder(bitrate=10000000)
output = PyavOutput("test.mp4")
picam2.start_recording(encoder, output)

time.sleep(5)

picam2.stop_recording()
