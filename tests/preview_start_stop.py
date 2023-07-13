#!/usr/bin/python3

import time

from picamera2 import Picamera2, Preview

picam2 = Picamera2()

picam2.start_preview(Preview.QTGL)
time.sleep(1)
picam2.stop_preview()
time.sleep(1)

picam2.start_preview(Preview.QTGL)
time.sleep(1)
picam2.stop_preview()
time.sleep(1)

picam2.start_preview(Preview.QT)
time.sleep(1)
picam2.stop_preview()
time.sleep(1)

picam2.start_preview(Preview.QT)
time.sleep(1)
picam2.stop_preview()
time.sleep(1)

picam2.start_preview(Preview.QTGL)
picam2.start()
time.sleep(2)
picam2.stop_preview()

picam2.stop()
