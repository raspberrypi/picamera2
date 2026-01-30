#!/usr/bin/python3

# Send an MPEG2 transport stream over a socket using PyavOutput.

import socket
import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import PyavOutput

picam2 = Picamera2()
video_config = picam2.create_video_configuration({"size": (1280, 720)})
picam2.configure(video_config)
encoder = H264Encoder(1000000)

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    sock.connect(("REMOTEIP", 10001))
    picam2.start_recording(encoder, PyavOutput(f"pipe:{sock.fileno()}", format="mpegts"))  # noqa
    time.sleep(20)
    picam2.stop_recording()
