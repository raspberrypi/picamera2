#!/usr/bin/python3
import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder

picam2 = Picamera2()
video_config = picam2.create_video_configuration()
picam2.configure(video_config)

encoder = H264Encoder(qp=30)

picam2.start_recording(encoder, 'test.h264')
time.sleep(5)
picam2.stop_recording()
