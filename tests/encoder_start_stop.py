#!/usr/bin/python3

import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput

picam2 = Picamera2()
encoder = H264Encoder(10000000)
picam2.start(picam2.create_video_configuration())

for i in range(40):
    print(i)
    encoder.output = FileOutput("test.h264")
    picam2.start_encoder(encoder)
    time.sleep(0.5)
    picam2.stop_encoder()
    time.sleep(0.5)

picam2.stop()
picam2.close()
