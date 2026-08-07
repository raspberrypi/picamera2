#!/usr/bin/python3

# Super-simple PyQt6 GL app forced to X11 via QT_QPA_PLATFORM=xcb.
# Verifies that the X11 GL widget (QGlPicamera2) is selected on xcb.

import os

try:
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
except ImportError:
    print("SKIPPED (no PyQt6)")
    quit()

from picamera2 import Picamera2
from picamera2.previews.qt import QGl6Picamera2, is_wayland_gl_widget

os.environ['QT_QPA_PLATFORM'] = 'xcb'

picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration())

app = QApplication([])

widget = QGl6Picamera2(picam2, width=640, height=480)
widget.setWindowTitle("QtGL PyQt6 X11")
widget.show()
picam2.start()


def check_and_quit():
    if is_wayland_gl_widget(widget):
        print("ERROR: expected X11 widget (QT_QPA_PLATFORM=xcb), got Wayland")
    app.quit()


QTimer.singleShot(3000, check_and_quit)
app.exec()
