#!/usr/bin/python3

from picamera2 import Picamera2

picam2 = Picamera2()

# Record a 5 second video.
picam2.start_and_record_video("test.mp4", duration=5)
