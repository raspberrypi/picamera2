#!/usr/bin/python3

# A simple demo script that monitors a scene and starts recording when
# motion is detected. Additionally, client can connect over the network
# and view a live image stream.
#
# This version of the script uses the PyavOutput class which allows us
# to record mp4 files directly, and to send MPEG-2 Transport Streams
# over the network.

import socket
import threading
import time

import numpy as np

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import CircularOutput2, PyavOutput

lsize = (320, 240)
picam2 = Picamera2()
main = {"size": (1280, 720), "format": "YUV420"}
lores = {"size": lsize, "format": "YUV420"}
video_config = picam2.create_video_configuration(main, lores=lores)
picam2.configure(video_config)
picam2.start_preview()
encoder = H264Encoder(bitrate=1000000, repeat=True)
duration = 3
circ = CircularOutput2(buffer_duration_ms=duration * 1000)
picam2.start()
picam2.start_recording(encoder, circ)

w, h = lsize
prev = None
encoding = False
ltime = 0


def server():
    global circ, picam2  # noqa
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", 10001))
        sock.listen()
        while tup := sock.accept():
            print("Connection received")
            conn, addr = tup
            output = PyavOutput(f"pipe:{conn.fileno()}", format="mpegts")  # noqa
            event = threading.Event()
            output.error_callback = lambda e: event.set()  # noqa
            output.start()
            encoder.output = [circ, output]
            event.wait()
            output.stop()
            print("Connection terminated")


t = threading.Thread(target=server, daemon=True)
t.start()

try:
    while True:
        cur = picam2.capture_array("lores")[:h, :w]
        if prev is not None:
            # Measure pixels differences between current and
            # previous frame
            mse = np.square(np.subtract(cur, prev)).mean()
            if mse > 7:
                if not encoding:
                    epoch = int(time.time())
                    circ.open_output(PyavOutput(f"{epoch}.mp4"))
                    encoding = True
                    print("New recording started: mse", mse)
                ltime = time.time()
            else:
                if encoding and time.time() - ltime > duration + 2:
                    circ.close_output()
                    print("Recording stopped")
                    encoding = False
        prev = cur

except KeyboardInterrupt:
    print("Finished")

finally:
    picam2.stop_recording()
