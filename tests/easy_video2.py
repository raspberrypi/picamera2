#!/usr/bin/python3

from picamera2 import Picamera2

picam2 = Picamera2()

# This format was missing previously:
picam2.video_configuration.format = 'BGR888'

# Record a 2 second video.
picam2.start_and_record_video("test.mp4", duration=2)
