#!/usr/bin/python3
import time

import numpy as np

from picamera2 import Picamera2
from picamera2.encoders.jpeg_encoder import JpegEncoder
from picamera2.outputs import CircularOutput

lsize = (320, 240)
camera = Picamera2()
video_config = camera.create_video_configuration(
    main={"size": (1280, 720), "format": "RGB888"},
    lores={"size": lsize, "format": "YUV420"},
)
camera.configure(video_config)
camera.start_preview()
encoder = JpegEncoder()
encoder.output = CircularOutput()
camera.encoder = encoder
camera.start()
camera.start_encoder()

w, h = lsize
prev = None
encoding = False
ltime = 0

for _ in range(4):
    cur = camera.capture_buffer("lores")
    cur = cur[: w * h].reshape(h, w)
    if prev is not None:
        # Measure pixels differences between current and
        # previous frame
        mse = np.square(np.subtract(cur, prev)).mean()
        if mse > 7:
            if not encoding:
                epoch = int(time.time())
                encoder.output.fileoutput = "{}.h264".format(epoch)
                encoder.output.start()
                encoding = True
                print("New Motion", mse)
            ltime = time.time()
        else:
            if encoding and time.time() - ltime > 5.0:
                encoder.output.stop()
                encoding = False
    prev = cur

camera.stop_encoder()
camera.close()
