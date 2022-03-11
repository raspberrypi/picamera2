#!/usr/bin/python3

from picamera2.previews.null_preview import *
from picamera2.encoders.h264_encoder import *
from picamera2.picamera2 import *
import time
import os

picam2 = Picamera2()
video_config = picam2.video_configuration()
picam2.configure(video_config)

picam2.start_preview(NullPreview())
encoder = H264Encoder(10000000)

picam2.start_recording(encoder, 'test.h264')
time.sleep(10)
picam2.stop_recording()
