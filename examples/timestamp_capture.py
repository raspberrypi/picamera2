#!/usr/bin/python3

import time

from picamera2 import Picamera2


def check_request_timestamp(request, check_time):
    md = request.get_metadata()
    # 'SensorTimestamp' is when the first pixel was read out, so it started being
    # exposed 'ExposureTime' earlier.
    exposure_start_time = md['SensorTimestamp'] - 1000 * md['ExposureTime']
    if exposure_start_time < check_time:
        print("ERROR: request captured too early by", check_time - exposure_start_time, "nanoseconds")


picam2 = Picamera2()
picam2.start()

time.sleep(1)

# Capture a request that is guaranteed not to have started being exposed before
# we make the request. Do it 30 times as a test. Note that this kind of thing is
# likely cut the apparent framerate because of all the stopping and waiting for sync.

for _ in range(30):
    check_time = time.monotonic_ns()
    request = picam2.capture_request(flush=True)
    check_request_timestamp(request, check_time)
    request.release()

# Capture a request where nothing started being exposed until 1/2s in the
# future. Do this 10 times as a test.

for _ in range(10):
    check_time = time.monotonic_ns() + 5e8
    request = picam2.capture_request(flush=check_time)
    check_request_timestamp(request, check_time)
    request.release()

# Let's do this last test again, but using asynchronous operation.

for _ in range(10):
    check_time = time.monotonic_ns() + 5e8
    job = picam2.capture_request(flush=check_time, wait=False)
    # Now we can do other stuff while waiting for the capture.
    request = picam2.wait(job)
    check_request_timestamp(request, check_time)
    request.release()
