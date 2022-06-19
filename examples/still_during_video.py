#!/usr/bin/python3

from picamera2.encoders import H264Encoder
from picamera2 import Picamera2
from picamera2.request import PostProcess
import time
import os

# Encode a VGA stream, and capture a higher resolution still image half way through.

picam2 = Picamera2()
post_process = PostProcess(picam2)
half_resolution = [dim // 2 for dim in picam2.sensor_resolution]
main_stream = {"size": half_resolution}
lores_stream = {"size": (640, 480)}
video_config = picam2.video_configuration(main_stream, lores_stream, encode="lores")
picam2.configure(video_config)

encoder = H264Encoder(10000000)

picam2.start_recording(encoder, 'test.h264')
time.sleep(5)

# It's better to capture the still in this thread, not in the one driving the camera.
request = picam2.capture_request()
post_process.save(post_process.make_image(request.make_buffer("main"), video_config["main"]), request.get_metadata(), "test.jpg")
request.release()
print("Still image captured!")

time.sleep(5)
picam2.stop_recording()
