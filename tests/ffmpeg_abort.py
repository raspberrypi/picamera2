#!/usr/bin/python3

# This test checks that the application gets notified when the FFmpeg process that
# it's outputting to disappears spontaneously. For example, when we're writing to
# a network socket that gets disconnected.

import socket
import time
from threading import Event, Thread

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput


def server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 12345))
        s.listen()
        conn, addr = s.accept()
        with conn:
            while not abort.is_set():
                conn.recv(1024)


def error_callback(e):
    notify.set()


abort = Event()
notify = Event()
thread = Thread(target=server)
thread.start()

picam2 = Picamera2()
config = picam2.create_video_configuration()
picam2.configure(config)

encoder = H264Encoder(bitrate=10000000)
# Suppress FFmpeg's error messages.
output = FfmpegOutput("-loglevel quiet -f h264 tcp://127.0.0.1:12345")
output.error_callback = error_callback
picam2.start_recording(encoder, output)
time.sleep(2)

# Now kill the server and see if we get notified that FFmpeg has died.
abort.set()
if not notify.wait(3):
    print("ERROR: no error callback from FfmpegOutput")
picam2.stop_recording()
