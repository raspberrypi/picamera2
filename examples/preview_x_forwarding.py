#!/usr/bin/python3

# The QtPreview uses software rendering and thus makes more use of the
# CPU, but it does work with X forwarding, unlike the QtGlPreview.

from PiCamera2.PiCamera2 import *
import time

picam2 = PiCamera2()
picam2.start_preview(Preview.QT)

preview_config = picam2.preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(5)
