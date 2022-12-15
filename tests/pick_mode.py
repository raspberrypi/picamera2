#!/usr/bin/python3

# Example of reading the available modes, and picking one with
# the highest framerate and a raw bit depth of at least 10

import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, Quality
from picamera2.outputs import FfmpegOutput

picam2 = Picamera2()

available_modes = picam2.sensor_modes
min_bit_depth = 10
available_modes = list(
    filter(lambda x: (x["bit_depth"] >= min_bit_depth), available_modes)
)
available_modes.sort(key=lambda x: x["fps"], reverse=True)
[print(i) for i in available_modes]
chosen_mode = available_modes[0]

picam2.video_configuration = picam2.create_video_configuration(
    raw={"size": chosen_mode["size"], "format": chosen_mode["format"].format}
)
picam2.configure("video")

encoder = H264Encoder()
output = FfmpegOutput("test.mp4")

# Set the fps
fps = chosen_mode["fps"]
picam2.set_controls({"FrameRate": fps})

picam2.start_recording(encoder, output, quality=Quality.LOW)

time.sleep(5)

picam2.stop_recording()
