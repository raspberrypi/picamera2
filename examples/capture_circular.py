#!/usr/bin/python3

# Demonstration of how to trigger a recording when motion is detected.
# The use of the circular buffer means that the recording captures from
# a few seconds before the motion is detected.
#
# Note that the CircularOutput2 is usually preferred over the older
# CircularOutput because you can record mp4 files directly, and even audio.
# See capture_circular_improved.py.

import time

import numpy as np

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import CircularOutput

lsize = (320, 240)
picam2 = Picamera2()
main = {"size": (1280, 720), "format": "RGB888"}
lores = {"size": lsize, "format": "YUV420"}
video_config = picam2.create_video_configuration(main, lores=lores)
picam2.configure(video_config)
picam2.start_preview()
encoder = H264Encoder(bitrate=1000000, repeat=True)
encoder.output = CircularOutput()
picam2.start()
picam2.start_encoder(encoder)

w, h = lsize
prev = None
encoding = False
ltime = 0

while True:
    # Just get the greyscale part of the YUV420 image.
    cur = picam2.capture_array("lores")[:h, :w]
    if prev is not None:
        # Measure pixels differences between current and
        # previous frame
        mse = np.square(np.subtract(cur, prev)).mean()
        if mse > 7:
            if not encoding:
                epoch = int(time.time())
                encoder.output.fileoutput = f"{epoch}.h264"
                encoder.output.start()
                encoding = True
                print("New Motion", mse)
            ltime = time.time()
        else:
            if encoding and time.time() - ltime > 5.0:
                encoder.output.stop()
                encoding = False
    prev = cur

picam2.stop_encoder()
