#!/usr/bin/python3

# Preview.QTGL_DIRECT requests the direct (QOpenGLWindow) renderer: on Wayland
# it renders straight to the window surface with no intermediate FBO blit,
# making it the fastest option at high resolutions.  On X11 it falls back to
# the standard Preview.QTGL path.
#
# Caveat (Wayland only): the native sub-window always stacks above sibling Qt
# widgets and cannot be clipped by non-rectangular masks.  For a viewfinder
# that fills its area this is fine; apps that float Qt widgets over the preview
# should use Preview.QTGL instead.

import time

from picamera2 import Picamera2, Preview

picam2 = Picamera2()
picam2.start_preview(Preview.QTGL_DIRECT)

preview_config = picam2.create_preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(5)
