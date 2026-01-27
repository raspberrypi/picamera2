#!/usr/bin/python3

# Shows how to use the remote module to process images in a separate process.
# This is doing a simple sum of the pixels in the image in a separate process.
# The results are then gathered by the main process and printed.

import multiprocessing as mp
import os
import queue
import threading
import time

import numpy as np

import picamera2
from picamera2 import Pool, RemoteMappedArray

IMAGE_COUNT = 100


def run(request):
    print(f"Recieved request in process {os.getpid()}")
    with RemoteMappedArray(request, "main") as m:
        s = np.sum(m.array)
        time.sleep(0.1)  # long calculation
        print(f"Sum of array: {s}")
    print(f"Processed request in process {os.getpid()}")
    return s


def gather_results(futures):
    for i in range(IMAGE_COUNT):
        future = futures.get()
        print(f"Recieved result {i + 1}: {future.result()}")


if __name__ == "__main__":
    mp.set_start_method("spawn")
    picam2 = picamera2.Picamera2()
    config = picam2.create_preview_configuration(buffer_count=16)

    with Pool(run, 16, picam2) as pool:
        # Start the camera after creating the pool so the camera doesn't timeout
        picam2.start(config)

        futures = queue.Queue()
        results_thread = threading.Thread(target=gather_results, args=(futures,))
        results_thread.start()

        for _ in range(IMAGE_COUNT):
            with picam2.captured_request() as request:
                future = pool.send(request)
                futures.put(future)

        results_thread.join()
