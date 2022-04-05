#!/usr/bin/python3

# Capture a PNG while still running in the preview mode.

from PiCamera2.PiCamera2 import *
import time

picam2 = PiCamera2()
picam2.start_preview(Preview.QTGL)

preview_config = picam2.preview_configuration(main={"size": (800, 600)})
picam2.configure(preview_config)

picam2.start()
time.sleep(2)

picam2.capture_file("test.png")
