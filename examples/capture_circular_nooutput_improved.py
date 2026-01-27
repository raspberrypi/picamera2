#!/usr/bin/python3
import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import CircularOutput2, PyavOutput

# This script shows how to record video to a circular buffer and then
# open a file to start recording the output. The use of the
# CircularOutput2 means we can record an mp4 file rather than an
# unformatted H.264 bitstream.


picam2 = Picamera2()
fps = 30
dur = 5
vconfig = picam2.create_video_configuration(controls={'FrameRate': fps})
picam2.configure(vconfig)
encoder = H264Encoder()
output = CircularOutput2(buffer_duration_ms=5000)
picam2.start_recording(encoder, output)
output.open_output(PyavOutput("file.mp4"))
time.sleep(dur)
output.stop()
