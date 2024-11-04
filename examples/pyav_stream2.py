#!/usr/bin/python3

import socket
from threading import Event

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import PyavOutput

picam2 = Picamera2()
video_config = picam2.create_video_configuration({"size": (1280, 720), 'format': 'YUV420'})
picam2.configure(video_config)

encoder = H264Encoder(bitrate=10000000)
encoder.audio = True

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", 8888))

    while True:
        print("Waiting")
        sock.listen()

        conn, addr = sock.accept()
        print("Connected")

        output = PyavOutput(f"pipe:{conn.fileno()}", format="mpegts")
        event = Event()
        output.error_callback = lambda e: event.set()  # noqa

        picam2.start_recording(encoder, output)

        event.wait()
        print("Disconnected")

        picam2.stop_recording()
