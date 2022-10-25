#!/usr/bin/python3

import time

import numpy as np
from picamera2 import Picamera2, Preview

picam2a = Picamera2(0)
picam2a.configure(picam2a.create_preview_configuration())
picam2a.start_preview(Preview.QTGL)

picam2b = Picamera2(1)
picam2b.configure(picam2b.create_preview_configuration())
picam2b.start_preview(Preview.QT)

picam2a.start()
picam2b.start()
time.sleep(10)
picam2a.stop_preview()
picam2b.stop_preview()

time.sleep(2)

overlay = np.zeros((300, 400, 4), dtype=np.uint8)
overlay[:150, 200:] = (255, 0, 0, 64)
overlay[150:, :200] = (0, 255, 0, 64)
overlay[150:, 200:] = (0, 0, 255, 64)

picam2a.start_preview(Preview.QTGL)
picam2b.start_preview(Preview.QT)
picam2a.set_overlay(overlay)
picam2b.set_overlay(overlay)

time.sleep(10)
