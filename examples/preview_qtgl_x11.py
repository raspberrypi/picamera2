#!/usr/bin/python3

# Preview.QTGL forced to the X11/XWayland path via QT_QPA_PLATFORM=xcb.
# Also tests that a simple overlay is alpha-blended correctly.

import os
import time

import numpy as np

from picamera2 import Picamera2, Preview

os.environ['QT_QPA_PLATFORM'] = 'xcb'

picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration())
picam2.start_preview(Preview.QTGL)
picam2.start()
time.sleep(1)

overlay = np.zeros((300, 400, 4), dtype=np.uint8)
overlay[:150, 200:] = (255, 0, 0, 64)
overlay[150:, :200] = (0, 255, 0, 64)
overlay[150:, 200:] = (0, 0, 255, 64)
picam2.set_overlay(overlay)
time.sleep(2)

if picam2.is_wayland_gl_preview():
    print("ERROR: expected X11 preview (QT_QPA_PLATFORM=xcb), got Wayland")
