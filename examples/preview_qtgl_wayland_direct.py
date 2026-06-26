#!/usr/bin/python3

# QtGlPreviewWaylandDirect is like QtGlPreviewWayland (a native-Wayland,
# GPU-accelerated Qt preview) but renders straight to the window surface using
# a QOpenGLWindow, avoiding the QOpenGLWidget FBO -> window blit. This is the
# fastest option, especially at high resolutions.
#
# Caveat: it uses a container/native window, which always stacks above sibling
# Qt widgets and can't be clipped by non-rectangular masks. For a viewfinder
# that fills its area this is fine (overlays are drawn inside the GL context);
# apps that float Qt widgets over the preview should use Preview.QTGL_WL.

import time

from picamera2 import Picamera2, Preview

picam2 = Picamera2()
picam2.start_preview(Preview.QTGL_WL_DIRECT)

preview_config = picam2.create_preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(5)
