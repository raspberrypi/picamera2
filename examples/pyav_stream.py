#!/usr/bin/python3

# Example using PyavOutput to serve an MPEG2 transport stream to TCP connections.
# Just point a stream playher at tcp://<Pi-ip-address>:8888

from threading import Event

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import PyavOutput

picam2 = Picamera2()
config = picam2.create_video_configuration({'size': (1280, 720), 'format': 'YUV420'})
picam2.configure(config)

event = Event()


def callback(e):
    event.set()


while True:
    encoder = H264Encoder(bitrate=10000000)
    output = PyavOutput("tcp://0.0.0.0:8888\?listen=1", format="mpegts")  # noqa
    output.error_callback = callback
    picam2.start_recording(encoder, output)

    event.wait()
    event.clear()
    print("Client disconnected")

    picam2.stop_recording()
