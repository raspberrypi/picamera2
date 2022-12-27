#!/usr/bin/python3

import socket
import time

from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput

camera = Picamera2()
video_config = camera.create_video_configuration({"size": (1920, 1080)})
camera.configure(video_config)
encoder = JpegEncoder()

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    sock.connect(("127.0.0.1", 10001))
    stream = sock.makefile("wb")
    camera.start_recording(encoder, FileOutput(stream))
    time.sleep(2)
    camera.stop_recording()

camera.close()
