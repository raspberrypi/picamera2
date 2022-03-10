#!/usr/bin/python3

import time
from picamera2.picamera2 import *
from picamera2.previews.null_preview import *

picam2 = Picamera2()
config = picam2.preview_configuration()
picam2.configure(config)

picam2.start_preview(NullPreview())

picam2.start()
time.sleep(1)
picam2.stop()

