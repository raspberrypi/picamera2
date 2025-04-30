#!/usr/bin/python3

import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import PyavOutput, SplittableOutput

picam2 = Picamera2()
config = picam2.create_video_configuration()
picam2.configure(config)
encoder = H264Encoder(bitrate=5000000)

splitter = SplittableOutput(output=PyavOutput("test0.mp4"))

# Start writing initially to one file, and then we'll switch seamlessly to another.
# You can omit the initial output, and use split_output later to start the first output.
picam2.start_recording(encoder, splitter)

time.sleep(5)

# This returns only when the split has happened and the first file has been closed.
# The second file is guaranteed to continue at an I frame with no frame drops.
print("Waiting for switchover...")
splitter.split_output(PyavOutput("test1.mp4"))
print("Switched to new output!")

time.sleep(5)

picam2.stop_recording()
