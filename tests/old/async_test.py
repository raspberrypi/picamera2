#!/usr/bin/python3
from concurrent.futures import Future, wait
from threading import Event, Thread
from typing import List

from scicamera import Camera
from scicamera.configuration import CameraConfig

camera = Camera()
config = CameraConfig.for_preview(camera)
camera.configure(config)
camera.start()
abort = Event()
started = Event()


def thread_func():
    n = 0
    while not abort.wait(0.1):
        camera.capture_metadata().result()
        n += 1
        started.set()
    print("Thread received", n, "frames")


threads = [Thread(target=thread_func, args=()) for _ in range(3)]

for thread in threads:
    thread.start()

try:
    futures: List[Future] = []
    for i in range(4):
        futures.append(camera.capture_metadata())
    wait(futures, timeout=10)
finally:
    abort.set()
    for thread in threads:
        thread.join()

    camera.stop()
    camera.close()

times = [job.result()["SensorTimestamp"] for job in futures]
times_sorted = sorted(times)
assert times == times_sorted, times
