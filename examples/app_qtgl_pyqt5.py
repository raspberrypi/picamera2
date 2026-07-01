#!/usr/bin/python3

# Super-simple PyQt5 GL preview app with default platform settings.
# Verifies that the factory selects the widget matching the active Qt backend.

try:
    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import QApplication
except ImportError:
    print("SKIPPED (no PyQt5)")
    quit()

from picamera2 import Picamera2
from picamera2.previews.qt import QGlPicamera2, is_wayland_gl_widget

picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration())

app = QApplication([])

widget = QGlPicamera2(picam2, width=640, height=480)
widget.setWindowTitle("QtGL PyQt5")
widget.show()
picam2.start()

expected_wayland = app.platformName() == 'wayland'


def check_and_quit():
    got_wayland = is_wayland_gl_widget(widget)
    if got_wayland != expected_wayland:
        platform = "Wayland" if expected_wayland else "X11"
        print(f"ERROR: expected {platform} widget (Qt5 active platform)")
    app.quit()


QTimer.singleShot(3000, check_and_quit)
app.exec()
