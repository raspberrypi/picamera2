#!/usr/bin/python3

import time

from picamera2 import CancelledError, Picamera2, TimeoutError

# At 2 fps should take over 3s to see the first frame.
controls = {'FrameRate': 2}

with Picamera2() as picam2:
    config = picam2.create_preview_configuration(controls=controls)
    picam2.start(config)
    t0 = time.monotonic()

    # Test that we time out correctly, and that we can cancel everything so
    # that we stop quickly.
    try:
        array = picam2.capture_array(wait=1.0)
    except TimeoutError:
        print("Timed out")
    else:
        print("ERROR: operation did not time out")

    t1 = time.monotonic()
    if t1 - t0 > 2.0:
        print("ERROR: time out appears to have taken too long")

    picam2.cancel_all_and_flush()
    picam2.stop()
    t2 = time.monotonic()
    print("Stopping took", t2 - t1, "seconds")
    if t2 - t1 > 0.1:
        print(f"ERROR: stopping took too long ({t2-t1} seconds)")

with Picamera2() as picam2:
    config = picam2.create_preview_configuration(controls=controls)
    picam2.start(config)
    t0 = time.monotonic()

    # Test that we can cancel a job and get a correct CancelledError.
    job = picam2.capture_array(wait=False)
    picam2.cancel_all_and_flush()

    try:
        array = job.get_result()
    except CancelledError:
        print("Job was cancelled")
    else:
        print("ERROR: job was not cancelled")

    t1 = time.monotonic()
    if t1 - t0 > 0.5:
        print("ERROR: job took too long to cancel")
