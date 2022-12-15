#!/usr/bin/python3

# The QtPreview uses software rendering and thus makes more use of the
# CPU, but it does work with X forwarding, unlike the QtGlPreview.

import time

from picamera2 import Picamera2, Preview

picam2 = Picamera2()
picam2.start_preview(Preview.QT)

preview_config = picam2.create_preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(5)
