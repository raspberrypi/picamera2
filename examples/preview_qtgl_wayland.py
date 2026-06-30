#!/usr/bin/python3

# Preview.QTGL automatically selects the best available renderer: on a native
# Wayland session it uses QOpenGLWidget (QGlPicamera2Wl) which composites
# natively without requiring an X server; on X11 it uses the raw-EGL path
# (QGlPicamera2).  Either way the zero-copy dmabuf import is used.
#
# To force the X11/XWayland path even on Wayland, run with:
#   QT_QPA_PLATFORM=xcb python preview_qtgl_wayland.py

import time

from picamera2 import Picamera2, Preview

picam2 = Picamera2()
picam2.start_preview(Preview.QTGL)

preview_config = picam2.create_preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(5)
