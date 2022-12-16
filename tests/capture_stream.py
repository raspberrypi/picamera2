#!/usr/bin/python3

import socket
import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput

picam2 = Picamera2()
video_config = picam2.create_video_configuration({"size": (1280, 720)})
picam2.configure(video_config)
encoder = H264Encoder(1000000)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", 10001))
    sock.listen()

    picam2.encoder = encoder

    conn, addr = sock.accept()
    stream = conn.makefile("wb")
    picam2.encoder.output = FileOutput(stream)
    picam2.start_encoder()
    picam2.start()
    time.sleep(20)
    picam2.stop()
    picam2.stop_encoder()
    conn.close()

picam2.close()
