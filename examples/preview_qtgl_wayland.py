#!/usr/bin/python3

# QtGlPreviewWayland is a GPU-accelerated Qt preview (like QtGlPreview) that
# also works as a *native* Wayland client, not only through XWayland.
#
# QtGlPreview renders raw EGL onto the widget's native window, which only works
# on X11; under a Wayland compositor it falls back to XWayland. QtGlPreviewWayland
# instead renders through Qt's own OpenGL context (QOpenGLWidget), so it needs no
# X server and composites natively. The zero-copy dmabuf import is unchanged.
#
# Select it with Preview.QTGL_WL. Prefer it when running under Wayland (e.g.
# labwc) and you want to avoid XWayland; on X11 the regular Preview.QTGL is the
# usual choice.

import time

from picamera2 import Picamera2, Preview

picam2 = Picamera2()
picam2.start_preview(Preview.QTGL_WL)

preview_config = picam2.create_preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(5)
