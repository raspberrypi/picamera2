#!/usr/bin/python3

# This script demonstrates how to capture video and audio simultaneously
# using the PyavOutput, which is the recommended technique for this.

import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import PyavOutput

picam2 = Picamera2()
video_config = picam2.create_video_configuration()
picam2.configure(video_config)

encoder = H264Encoder(bitrate=10000000)
encoder.audio = True
output = PyavOutput('test.mp4')

picam2.start_recording(encoder, output)
time.sleep(10)
picam2.stop_recording()
