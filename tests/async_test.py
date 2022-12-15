#!/usr/bin/python3

from picamera2 import Picamera2
from threading import Thread
import time

picam2 = Picamera2()
config = picam2.create_preview_configuration(queue=False)
picam2.configure(config)
picam2.start()
abort = False


def thread_func(delay):
    n = 0
    while not abort:
        picam2.capture_array()
        n += 1
        time.sleep(delay)
    print("Thread received", n, "frames")


delays = [0.1, 0.07, 0.15]

threads = [Thread(target=thread_func, args=(d,)) for d in delays]

for thread in threads:
    thread.start()

time.sleep(5)

jobs = []
for i in range(10):
    jobs.append(picam2.capture_metadata(wait=False))
    time.sleep(0.01)
times = [job.get_result()["SensorTimestamp"] for job in jobs]
diffs = [(t1 - t0) // 1000 for t0, t1 in zip(times[:-1], times[1:])]
print(diffs)
if any(d < 0 for d in diffs):
    print("Error: unexpected frame times")

time.sleep(5)

abort = True
for thread in threads:
    thread.join()

picam2.stop()
