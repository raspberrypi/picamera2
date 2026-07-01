#!/usr/bin/python3

# Super-simple PyQt6 GL preview app with default platform settings.
# Qt6 auto-selects Wayland when WAYLAND_DISPLAY is set, X11 otherwise.

try:
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
except ImportError:
    print("SKIPPED (no PyQt6)")
    quit()

from picamera2 import Picamera2
from picamera2.previews.qt import QGl6Picamera2, is_wayland_gl_widget

picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration())

app = QApplication([])

widget = QGl6Picamera2(picam2, width=640, height=480)
widget.setWindowTitle("QtGL PyQt6")
widget.show()
picam2.start()

expected_wayland = app.platformName() == 'wayland'


def check_and_quit():
    got_wayland = is_wayland_gl_widget(widget)
    if got_wayland != expected_wayland:
        platform = "Wayland" if expected_wayland else "X11"
        print(f"ERROR: expected {platform} widget (Qt6 active platform)")
    app.quit()


QTimer.singleShot(3000, check_and_quit)
app.exec()
