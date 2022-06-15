#!/usr/bin/python3
import time

import cv2

from picamera2 import MappedArray, Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput

picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration())

colour = (0, 255, 0)
origin = (0, 30)
font = cv2.FONT_HERSHEY_SIMPLEX
scale = 1
thickness = 2


def apply_timestamp(request):
    timestamp = time.strftime("%Y-%m-%d %X")
    with MappedArray(request, "main") as m:
        cv2.putText(m.array, timestamp, origin, font, scale, colour, thickness)


picam2.pre_callback = apply_timestamp

encoder = H264Encoder(10000000)

picam2.start_recording(encoder, "test.h264")
time.sleep(5)
picam2.stop_recording()
