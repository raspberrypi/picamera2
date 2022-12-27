#!/usr/bin/python3

import time
from concurrent.futures import Future
from threading import Thread
from typing import List

from picamera2 import Picamera2

camera = Picamera2()
config = camera.create_preview_configuration(queue=False)
camera.configure(config)
camera.start()
abort = False


def thread_func(delay):
    n = 0
    while not abort:
        camera.capture_array()
        n += 1
        time.sleep(delay)
    print("Thread received", n, "frames")


delays = [0.1, 0.07, 0.15]

threads = [Thread(target=thread_func, args=(d,)) for d in delays]

for thread in threads:
    thread.start()

time.sleep(2)

jobs: List[Future] = []
for i in range(4):
    jobs.append(camera.capture_metadata_async())
    time.sleep(0.01)

times = [job.result()["SensorTimestamp"] for job in jobs]
diffs = [(t1 - t0) // 1000 for t0, t1 in zip(times[:-1], times[1:])]
print(diffs)
if any(d < 0 for d in diffs):
    print("Error: unexpected frame times")

time.sleep(2)

abort = True
for thread in threads:
    thread.join()

camera.stop()
camera.close()
