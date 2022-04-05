#!/usr/bin/python3

# For use from the login console, when not running X Windows.

from PiCamera2.PiCamera2 import *
import time

picam2 = PiCamera2()
picam2.start_preview(Preview.DRM, x=100, y=100, width=640, height=480)

preview_config = picam2.preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(5)
