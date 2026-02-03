#!/usr/bin/python3

# This example script uses the FfmpegOutput to create an mp4 file, which
# is no longer the recommended method. Please see pyav_capture.py which
# uses the PyavOutput.

import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput

picam2 = Picamera2()
video_config = picam2.create_video_configuration()
picam2.configure(video_config)

encoder = H264Encoder(10000000)
output = FfmpegOutput('test.mp4')

picam2.start_recording(encoder, output)
time.sleep(10)
picam2.stop_recording()
