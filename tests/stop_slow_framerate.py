#!/usr/bin/python3

import time

from picamera2 import Picamera2

picam2 = Picamera2()
config = picam2.create_preview_configuration(
    controls={'FrameRate': 0.2, 'ExposureTime': 5000, 'AnalogueGain': 1.0, 'ColourGains': (1, 1)})
picam2.configure(config)
picam2.start()

md = picam2.capture_metadata()
t0 = time.clock_gettime(time.CLOCK_REALTIME)
md = picam2.capture_metadata()
t1 = time.clock_gettime(time.CLOCK_REALTIME)
print("Frame took", t1 - t0, "seconds")
if t1 - t0 < 4:
    print("ERROR: frame arrived too quickly", t1 - t0, "seconds")

picam2.stop()
t2 = time.clock_gettime(time.CLOCK_REALTIME)
print("Stopping took", t2 - t1, "seconds")
if t2 - t1 > 0.5:
    print("ERROR: stop took too long", t2 - t1, "seconds")
