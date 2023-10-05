#!/usr/bin/python3
import time

from picamera2 import Picamera2
from picamera2.encoders import Encoder
from picamera2.outputs import Output

picam2 = Picamera2()
picam2.configure()
encoder = Encoder()
output = Output()
picam2.start_recording(encoder, output)
time.sleep(5)
picam2.stop_recording()
