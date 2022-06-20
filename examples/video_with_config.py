#!/usr/bin/python3

# Use the configuration structure method to do a full res capture.

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
import time

picam2 = Picamera2()

# We don't really need to change anyhting, but let's mess around just as a test.
picam2.video_configuration.size = (800, 480)
picam2.video_configuration.format = "YUV420"
encoder = H264Encoder(bitrate=1000000)

picam2.start_recording(encoder, "test.h264", config="video")
time.sleep(5)
picam2.stop_recording()
