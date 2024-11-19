#!/usr/bin/python3

# Example using PyavOutput through a circular buffer to capture files.

import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import CircularOutput2, PyavOutput

picam2 = Picamera2()
config = picam2.create_video_configuration({'size': (1280, 720), 'format': 'YUV420'})
picam2.configure(config)

encoder = H264Encoder(bitrate=10000000)
circular = CircularOutput2(buffer_duration_ms=5000)
picam2.start_recording(encoder, circular)

time.sleep(5)

# This will capture the video from "buffer_duration_ms" (5 seconds) ago.
circular.open_output(PyavOutput("test1.mp4"))
time.sleep(5)
circular.close_output()

# Because this is not closed when we circular buffer stops, the remaining 5 seconds
# will get flushed into here.
circular.open_output(PyavOutput("test2.mp4"))
picam2.stop_recording()
