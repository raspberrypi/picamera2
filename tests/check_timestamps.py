#!/usr/bin/python3
import time

import numpy as np

from picamera2 import CameraConfig, Picamera2

camera = Picamera2()
video_config = CameraConfig.for_video(camera)
camera.configure(video_config)

timestamps = []

camera.add_request_callback(lambda r: timestamps.append(time.time() * 1e6))

camera.start()
camera.discard_frames(10).result()
camera.stop()

# Now let's analyse all the timestamps
diffs = timestamps[:-1] - timestamps[1:]
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
camera.close()
