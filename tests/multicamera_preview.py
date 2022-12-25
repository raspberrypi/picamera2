#!/usr/bin/python3

import time

import numpy as np

from picamera2 import Picamera2, Preview

picam2a = Picamera2(0)
picam2a.configure(picam2a.create_preview_configuration())
picam2a.start_preview(Preview.NULL)

picam2b = Picamera2(1)
picam2b.configure(picam2b.create_preview_configuration())
picam2b.start_preview(Preview.NULL)

picam2a.start()
picam2b.start()
time.sleep(2)
picam2a.stop_preview()
picam2b.stop_preview()

time.sleep(2)

picam2a.start_preview(Preview.NULL)
picam2b.start_preview(Preview.NULL)

time.sleep(2)
picam2a.close()
picam2b.close()
