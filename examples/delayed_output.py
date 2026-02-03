#! /usr/bin/python3

# Shows how an encoder can be started, but no output attached until later.
# The output will drop frames until it sees the first I-frame.

import os
import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import PyavOutput

picam2 = Picamera2()

config = picam2.create_video_configuration()
encoder = H264Encoder(bitrate=10000000)

picam2.start_recording(encoder, None)

time.sleep(5)

output = PyavOutput("test.mp4")
output.start()
encoder.output = output
print("Output attached")

time.sleep(5)

picam2.stop_recording()

if not os.path.isfile("test.mp4"):
    print("ERROR: output file not created")
