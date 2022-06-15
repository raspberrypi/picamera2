#!/usr/bin/python3

import time

from picamera2 import Picamera2, Preview

picam2 = Picamera2()
config = picam2.create_preview_configuration()
picam2.configure(config)

# In fact, picam2.start() would do this anyway for us:
picam2.start_preview(Preview.NULL)

picam2.start()
time.sleep(1)
picam2.stop()
