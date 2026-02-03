#!/usr/bin/python3

# This is the most high level way to capture and save a video. Howwever,
# the API gives you less control over the camera system so we would recommend
# it only to folks with the simplest use-cases.

from picamera2 import Picamera2

picam2 = Picamera2()

# Record a 5 second video.
picam2.start_and_record_video("test.mp4", duration=5)
