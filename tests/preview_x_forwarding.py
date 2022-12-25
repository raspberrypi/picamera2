#!/usr/bin/python3

# The QtPreview uses software rendering and thus makes more use of the
# CPU, but it does work with X forwarding, unlike the QtGlPreview.

import time

from picamera2 import Picamera2, Preview

camera = Picamera2()
camera.start_preview(Preview.NULL)

preview_config = camera.create_preview_configuration()
camera.configure(preview_config)

camera.start()
time.sleep(1)
camera.stop()

camera.close()
