#!/usr/bin/python3

from picamera2.encoders.h264_encoder import *
from picamera2.picamera2 import *
import time
import os

lsize = (320, 240)
picam2 = Picamera2()
video_config = picam2.video_configuration(main={"size": (1280, 720), "format": "RGB888"},
                                          lores={"size": lsize, "format": "YUV420"})
picam2.configure(video_config)
picam2.start_preview()
encoder = H264Encoder(1000000)
encoder.buffersize = 30 * 5
encoder.output = open("/dev/null", 'wb')
picam2.encoder = encoder
picam2.start()
picam2.start_encoder()

w, h = lsize
prev = None
encoding = False
ltime = 0

while True:
    cur = picam2.capture_buffer("lores")
    cur = cur[:w * h].reshape(h, w)
    if prev is not None:
        # Measure pixels differences between current and
        # previous frame
        mse = np.square(np.subtract(cur, prev)).mean()
        if mse > 7:
            if not encoding:
                epoch = int(time.time())
                encoder.dumpbuffer("{}-before.h264".format(epoch))
                encoder.output = open("{}.h264".format(epoch), 'wb')
                encoding = True
                print("New Motion", mse)
            ltime = time.time()
        else:
            if encoding and time.time() - ltime > 5.0:
                encoder.output = open("/dev/null", 'wb')
                encoding = False
    prev = cur

picam2.stop_encoder()
