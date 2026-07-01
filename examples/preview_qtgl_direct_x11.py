#!/usr/bin/python3

# Preview.QTGL_DIRECT forced to the X11/XWayland path via QT_QPA_PLATFORM=xcb.
# On X11 QTGL_DIRECT falls back to the standard QTGL (QGlPicamera2) path.

import os
import time

from picamera2 import Picamera2, Preview

os.environ['QT_QPA_PLATFORM'] = 'xcb'

picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration())
picam2.start_preview(Preview.QTGL_DIRECT)
picam2.start()
time.sleep(3)

if picam2.is_wayland_gl_preview():
    print("ERROR: expected X11 preview (QT_QPA_PLATFORM=xcb), got Wayland")
