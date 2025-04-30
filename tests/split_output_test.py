#!/usr/bin/python3

# We're going to encode a video stream, splitting it seamlessly into a pair of
# files using the SplittableOutput. At the same time we'll write a single output
# file as well, and check that the split files contain as much as the single file.

import io
import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput, SplittableOutput

picam2 = Picamera2()
config = picam2.create_video_configuration()
picam2.configure(config)

first_half = io.BytesIO()
second_half = io.BytesIO()
whole = io.BytesIO()

encoder = H264Encoder(bitrate=5000000)
splitter = SplittableOutput(output=FileOutput(first_half))
output = FileOutput(whole)
encoder.output = [splitter, output]

picam2.start_encoder(encoder)
picam2.start()

time.sleep(5)

splitter.split_output(FileOutput(second_half))

time.sleep(5)

picam2.stop_recording()

first_half_len = first_half.getbuffer().nbytes
second_half_len = second_half.getbuffer().nbytes
combined_len = first_half_len + second_half_len
whole_len = whole.getbuffer().nbytes

print("First half:", first_half_len)
print("Second half:", second_half_len)
print("Both halves combined:", combined_len)
print("Whole output:", whole_len)

if combined_len != whole_len:
    print("Error: split files do not match the whole file")
else:
    print("Files match!")
