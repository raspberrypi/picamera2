#!/usr/bin/python3
import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import CircularOutput

picam2 = Picamera2()
fps = 30
dur = 5
micro = int((1 / fps) * 1000000)
vconfig = picam2.create_video_configuration()
vconfig['controls']['FrameDurationLimits'] = (micro, micro)
picam2.configure(vconfig)
encoder = H264Encoder()
output = CircularOutput(buffersize=int(fps * (dur + 0.2)), outputtofile=False)
picam2.start_recording(encoder, output)
time.sleep(dur * 3)

with open("test.h264", "wb") as out:
    for frame, _ in output.copyandclear():
        out.write(frame)

time.sleep(dur * 3)

with open("test2.h264", "wb") as out:
    for frame, _ in output.copyandclear():
        out.write(frame)
