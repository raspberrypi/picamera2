#!/usr/bin/python3

# The QtPreview uses software rendering and thus makes more use of the
# CPU, but it does work with X forwarding, unlike the QtGlPreview.

from picamera2.previews.qt_preview import *
from picamera2.picamera2 import *
import time

picam2 = Picamera2()
picam2.start_preview(QtPreview())

preview_config = picam2.preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(5)
