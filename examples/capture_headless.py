#!//usr/bin/python3

from picamera2.picamera2 import *
from picamera2.previews.null_preview import *

picam2 = Picamera2()
config = picam2.still_configuration()
picam2.configure(config)

picam2.start_preview(NullPreview())

picam2.start()

np_array = picam2.capture_array()
print(np_array)
picam2.capture_file("demo.jpg")
picam2.stop()
