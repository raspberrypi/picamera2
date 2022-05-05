#!/usr/bin/python3
import time

from picamera2.encoders.h264_encoder import H264Encoder
from picamera2.picamera2 import Picamera2

picam2 = Picamera2()
video_config = picam2.video_configuration()
picam2.configure(video_config)

picam2.start_preview()
encoder = H264Encoder(10000000)

picam2.start_recording(encoder, 'test.h264')
time.sleep(10)
picam2.stop_recording()
