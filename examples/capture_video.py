#!/usr/bin/python3

from null_preview import *
from h264_encoder import *
from picamera2 import *
import time
import os

picam2 = Picamera2()
video_config = picam2.video_configuration()
picam2.configure(video_config)

preview = NullPreview(picam2)
encoder = H264Encoder(10000000)

picam2.start_recording(encoder, 'test.h264')
time.sleep(10)
picam2.stop_recording()
