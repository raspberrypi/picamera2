#!/usr/bin/python3
import time

from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput
from picamera2 import Picamera2

picam2 = Picamera2()
video_config = picam2.video_configuration()
picam2.configure(video_config)

encoder = H264Encoder(10000000)
output = FfmpegOutput('test.mp4')

picam2.start_recording(encoder, output)
time.sleep(10)
picam2.stop_recording()
