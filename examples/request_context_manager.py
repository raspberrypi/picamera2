#!/usr/bin/python3

# Demonstrate use of a context manager with "captured_request()". This is convenient because
# requests are released automatically for you.

from picamera2 import Picamera2

with Picamera2() as picam2:
    picam2.start()

    for _ in range(25):
        with picam2.captured_request() as request:
            print(request)
        with picam2.captured_request(flush=True) as request:
            print(request)
