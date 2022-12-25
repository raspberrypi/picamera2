#!/usr/bin/python3

# Use the configuration structure method to do a full res capture.

import time

from picamera2 import Picamera2
from picamera2.encoders.jpeg_encoder import JpegEncoder

picam2 = Picamera2()

# We don't really need to change anyhting, but let's mess around just as a test.
picam2.video_configuration.size = (800, 480)
picam2.video_configuration.format = "YUV420"
encoder = JpegEncoder()

picam2.start_recording(encoder, "test.h264", config="video")
time.sleep(5)
picam2.stop_recording()
