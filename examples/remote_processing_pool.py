#!/usr/bin/python3

# Shows how the Pool class can be used to process images in separate processes.
# This program creates a pool of 16 processes and sends 100 requests to the pool.
# It keeps track of the number of requests processed by each process and prints the results.

import os
import time

import picamera2
from picamera2 import Pool


def init():
    global counter
    counter = 0


def run(request):
    global counter
    counter += 1
    time.sleep(0.5)
    return (os.getpid(), counter)


if __name__ == "__main__":
    picam2 = picamera2.Picamera2()
    config = picam2.create_preview_configuration(buffer_count=16)
    futures = []

    with Pool(run, 16, picam2, init) as pool:
        # Start the camera after creating the pool so the camera doesn't timeout
        picam2.start(config)

        for _ in range(100):
            with picam2.captured_request() as request:
                future = pool.send(request)
                futures.append(future)

    print("Pool Closed")

    counts = {}
    counts.update(future.result() for future in futures)

    print(counts)
