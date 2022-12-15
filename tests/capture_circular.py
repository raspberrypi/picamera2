#!/usr/bin/python3
import time

import numpy as np

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import CircularOutput

lsize = (320, 240)
picam2 = Picamera2()
video_config = picam2.create_video_configuration(
    main={"size": (1280, 720), "format": "RGB888"},
    lores={"size": lsize, "format": "YUV420"},
)
picam2.configure(video_config)
picam2.start_preview()
encoder = H264Encoder(1000000, repeat=True)
encoder.output = CircularOutput()
picam2.encoder = encoder
picam2.start()
picam2.start_encoder()

w, h = lsize
prev = None
encoding = False
ltime = 0

while True:
    cur = picam2.capture_buffer("lores")
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

picam2.stop_encoder()
