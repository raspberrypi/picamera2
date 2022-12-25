#!/usr/bin/python3
import time

from picamera2 import Picamera2
from picamera2.encoders.jpeg_encoder import JpegEncoder
from picamera2.outputs import CircularOutput

camera = Picamera2()
fps = 30
dur = 5

micro = int((1 / fps) * 1000000)
vconfig = camera.create_video_configuration()
vconfig["controls"]["FrameDurationLimits"] = (micro, micro)

camera.configure(vconfig)
encoder = JpegEncoder()
output = CircularOutput(buffersize=int(fps * (dur + 0.2)), outputtofile=False)
output.fileoutput = "file.mjpeg"
camera.start_recording(encoder, output)
time.sleep(dur)
camera.stop_recording()
output.stop()

camera.close()
