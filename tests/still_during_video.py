#!/usr/bin/python3

import os
import time

from picamera2 import Picamera2
from picamera2.encoders.jpeg_encoder import JpegEncoder

# Encode a VGA stream, and capture a higher resolution still image half way through.

camera = Picamera2()
half_resolution = [dim // 2 for dim in camera.sensor_resolution]
main_stream = {"size": half_resolution}
lores_stream = {"size": (640, 480)}
video_config = camera.create_video_configuration(
    main_stream, lores_stream, encode="lores"
)
camera.configure(video_config)

encoder = JpegEncoder()

camera.start_recording(encoder, "test.h264")
time.sleep(2)

# It's better to capture the still in this thread, not in the one driving the camera.
request = camera.capture_request()
request.save("main", "test.jpg")
request.release()
print("Still image captured!")

time.sleep(2)
camera.stop_recording()
