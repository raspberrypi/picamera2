#!/usr/bin/python3

from null_preview import *
from h264_encoder import *
from picamera2 import *
import socket
import time
import os

picam2 = Picamera2()
video_config = picam2.video_configuration({"size": (1280, 720)})
picam2.configure(video_config)
preview = NullPreview(picam2)
encoder = H264Encoder(1000000)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", 10001))
    sock.listen()

    picam2.encoder = encoder
    picam2.start_encoder()
    picam2.start()

    conn, addr = sock.accept()
    stream = conn.makefile("wb")
    picam2.encoder.output = stream
    time.sleep(20)
    picam2.stop()
    picam2.stop_encoder()
    conn.close()
