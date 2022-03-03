#!/usr/bin/python3

from null_preview import *
from h264_encoder import *
from picamera2 import *
from signal import pause
import numpy as np
import time

picam2 = Picamera2()
video_config = picam2.video_configuration(main={"size": (1280, 720), "format": "RGB888"}, 
                                          lores={"size":(320,240), "format": "YUV420"})
picam2.configure(video_config)

prev = None 
encoding = False
ltime = time.time()

def rgb2gray(rgb):
    return np.dot(rgb[...,:3], [0.2989, 0.5870, 0.1140])

def request_callback(request):
    global prev, encoding, ltime
    
    # Extract lores buffer and convert from
    # YUV420 to RGB and then to greyscale
    arr = request.make_buffer("lores")
    config = request.picam2.camera_config["lores"]
    fmt = config["format"]
    w, h = config["size"]
    stride = config["stride"]
    arr = rgb2gray(YUV420_to_RGB(arr, (w, h)))

    if prev is not None:
        # Measure pixels differences between current and
        # previous frame
        mse = np.square(np.subtract(arr, prev)).mean()
        if mse > 7:
            if not encoding:
                encoder.output = open("{}.h264".format(int(time.time())), 'wb')
                picam2.start_encoder()
                encoding = True
            ltime = time.time()
            print("Motion")
        else:
            if encoding and time.time() - ltime > 2.0:
                picam2.stop_encoder()
                encoding = False
    prev = arr

picam2.request_callback = request_callback

preview = NullPreview(picam2)
encoder = H264Encoder(1000000)
picam2.encoder = encoder
picam2.start()

pause()
