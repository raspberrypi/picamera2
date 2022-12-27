#!/usr/bin/python3

import time

from picamera2 import Picamera2
from picamera2.encoders.jpeg_encoder import JpegEncoder
from picamera2.outputs import FileOutput

camera = Picamera2()
encoder = JpegEncoder()
camera.start(camera.create_video_configuration())

for i in range(40):
    print(i)
    encoder.output = FileOutput("test.h264")
    camera.start_encoder(encoder)
    time.sleep(0.5)
    camera.stop_encoder()
    time.sleep(0.5)

camera.stop()
camera.close()
