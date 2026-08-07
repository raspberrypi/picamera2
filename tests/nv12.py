#!/usr/bin/python3

# Check that the "NV12" pixel format works.

import time

from picamera2 import Picamera2, Preview
from picamera2.encoders import H264Encoder
from picamera2.outputs import PyavOutput

picam2 = Picamera2()
config = picam2.create_video_configuration({'format': 'NV12', 'size': (640, 360)})
picam2.configure(config)

picam2.start_preview(Preview.QTGL)
picam2.start()

time.sleep(1)

picam2.stop_preview()
picam2.start_preview(Preview.QT)

time.sleep(1)

picam2.stop_preview()
picam2.start_preview()

time.sleep(1)

picam2.capture_file("check.jpg")

encoder = H264Encoder(bitrate=5000000)
output = PyavOutput("check.mp4")
picam2.start_recording(encoder, output)

time.sleep(5)

picam2.stop_recording()
