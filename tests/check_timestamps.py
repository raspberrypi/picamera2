#!/usr/bin/python3
import time

import numpy as np

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import Output


class TimestampCollector(Output):
    "Output class that doesn't output anything but collects frame timestamps"

    def outputframe(self, frame, keyframe=True, timestamp=None):
        if timestamp is not None:
            timestamps.append(timestamp)


picam2 = Picamera2()
video_config = picam2.create_video_configuration()
picam2.configure(video_config)

encoder = H264Encoder(bitrate=10000000)
output = TimestampCollector()
timestamps = []

picam2.start_recording(encoder, output)
time.sleep(5)
picam2.stop_recording()

# Now let's analyse all the timestamps
diffs = np.array([next - now for now, next in zip(timestamps, timestamps[1:])])
median = np.median(diffs)
tol = median / 10
hist, _ = np.histogram(
    diffs,
    bins=[
        0,
        median - tol,
        median + tol,
        2 * median + tol,
        max(3 * median, diffs.max()),
    ],
)
print("[Early, expected, late, very late] =", hist)

if abs(median - 33333) > tol:
    raise RuntimeError(f"Frame intervals are {median}us but should be 33333us")
if hist[0] > 0:
    raise RuntimeError(f"{hist[0]} frame times less than the expected interval")
if hist[2] > 3:
    raise RuntimeError(f"Unexpectedly large number ({hist[2]}) of late frames")
if hist[3] > 0:
    raise RuntimeError(f"{hist[3]} very late frames detected")
picam2.close()
