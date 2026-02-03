#!/usr/bin/python3

# Demonstration of how to trigger a recording when motion is detected.
# The use of the circular buffer means that the recording captures from
# a few seconds before the motion is detected.
#
# The use of the CircularOutput2 means we can record directly to mp4 files.

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
duration = 3
encoder = H264Encoder(bitrate=1000000, repeat=True)
output = CircularOutput2(buffer_duration_ms=duration * 1000)
picam2.start_recording(encoder, output)

w, h = lsize
prev = None
encoding = False
ltime = 0

try:

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
                    output.open_output(PyavOutput(f"{epoch}.mp4"))
                    encoding = True
                    print("New recording started: mse", mse)
                ltime = time.time()
            else:
                if encoding and time.time() - ltime > duration + 2:
                    output.close_output()
                    print("Recording stopped")
                    encoding = False
        prev = cur

except KeyboardInterrupt:
    print("Finished")

finally:
    picam2.stop_recording()
