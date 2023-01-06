#!/usr/bin/python3

import time

from picamera2 import Picamera2, Preview


def click_close_button():
    # Nasty hack just for testing, emulate clicking the window close button
    picam2._preview.qpicamera2.close()


picam2 = Picamera2()

picam2.start_preview(Preview.QTGL)
time.sleep(1)
click_close_button()
time.sleep(1)

picam2.start_preview(Preview.QTGL)
time.sleep(1)
click_close_button()
time.sleep(1)

picam2.start_preview(Preview.QT)
time.sleep(1)
click_close_button()
time.sleep(1)

picam2.start_preview(Preview.QT)
time.sleep(1)
click_close_button()
time.sleep(1)

picam2.start_preview(Preview.QTGL)
picam2.start()
time.sleep(2)
click_close_button()

picam2.stop()
