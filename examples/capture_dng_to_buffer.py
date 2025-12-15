#!/usr/bin/python3

import io
import time

from picamera2 import Picamera2

picam2 = Picamera2()
config = picam2.create_still_configuration()
picam2.configure(config)
picam2.start()

time.sleep(1)

buf = io.BytesIO()
picam2.capture_file(buf, name='raw')

if len(buf.getbuffer()) == 0:
    print("ERROR: DNG buffer is empty")
