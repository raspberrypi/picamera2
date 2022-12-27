#!/usr/bin/python3

# Example of reading the available modes, and picking one with
# the highest framerate and a raw bit depth of at least 10

import time

from picamera2 import Picamera2
from picamera2.encoders import Quality
from picamera2.encoders.jpeg_encoder import JpegEncoder
from picamera2.outputs import FileOutput

camera = Picamera2()

available_modes = camera.sensor_modes
min_bit_depth = 10
available_modes = list(
    filter(lambda x: (x["bit_depth"] >= min_bit_depth), available_modes)
)
available_modes.sort(key=lambda x: x["fps"], reverse=True)
[print(i) for i in available_modes]
chosen_mode = available_modes[0]

camera.video_configuration = camera.create_video_configuration(
    raw={"size": chosen_mode["size"], "format": chosen_mode["format"].format}
)
camera.configure("video")

encoder = JpegEncoder()
output = FileOutput("test.raw")

# Set the fps
fps = chosen_mode["fps"]
camera.set_controls({"FrameRate": fps})

camera.start_recording(encoder, output, quality=Quality.LOW)

time.sleep(5)

camera.stop_recording()
