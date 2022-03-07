#!/usr/bin/python3

from picamera2 import *
from null_preview import *

picam2 = Picamera2(verbose_log=1)
config = picam2.still_configuration()
picam2.configure(config)

preview = NullPreview(picam2)

picam2.start()

np_array = picam2.capture_array()
print(np_array)
picam2.capture_file("demo.jpg")
picam2.stop()
