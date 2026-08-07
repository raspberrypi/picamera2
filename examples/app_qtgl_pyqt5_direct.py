#!/usr/bin/python3

# Super-simple PyQt5 GL preview app using the Wayland-direct renderer
# (QGlPicamera2WlDirect).  Forces QT_QPA_PLATFORM=wayland so Qt5 uses its
# Wayland backend; passes direct=True to select the QOpenGLWindow path.

import os

if not os.environ.get('WAYLAND_DISPLAY'):
    print("SKIPPED (no Wayland display)")
    quit()

try:
    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import QApplication
except ImportError:
    print("SKIPPED (no PyQt5)")
    quit()

from picamera2 import Picamera2
from picamera2.previews.qt import QGlPicamera2, is_wayland_gl_widget

os.environ['QT_QPA_PLATFORM'] = 'wayland'

picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration())

app = QApplication([])

widget = QGlPicamera2(picam2, direct=True, width=640, height=480)
widget.setWindowTitle("QtGL PyQt5 Wayland Direct")
widget.show()
picam2.start()


def check_and_quit():
    if not is_wayland_gl_widget(widget):
        print("ERROR: expected Wayland direct widget (QT_QPA_PLATFORM=wayland, direct=True), got X11")
    app.quit()


QTimer.singleShot(3000, check_and_quit)
app.exec()
