#!/usr/bin/python3

import socket
import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput

Picamera2.set_logging()
picam2 = Picamera2()
video_config = picam2.create_video_configuration({"size": (1920, 1080)})
picam2.configure(video_config)
encoder = H264Encoder(50000000)

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    sock.connect(("127.0.0.1", 10001))
    stream = sock.makefile("wb")
    picam2.start_recording(encoder, FileOutput(stream))
    time.sleep(5)
    picam2.stop_recording()
