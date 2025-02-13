#!/usr/bin/python3

# Start a Qt application, and use an asynchronous thread to "click" on the GUI.
# As app_test.py, but using PyQt6 instead of PyQt5.

import threading
import time

from PyQt6 import QtCore
from PyQt6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QPushButton,
                             QVBoxLayout, QWidget)

from picamera2 import Picamera2
from picamera2.previews.qt import QGl6Picamera2 as QGlPicamera2


def post_callback(request):
    label.setText(''.join(f"{k}: {v}\n" for k, v in request.get_metadata().items()))


Picamera2.set_logging()
picam2 = Picamera2()
picam2.post_callback = post_callback
picam2.configure(picam2.create_preview_configuration(main={"size": (800, 600)}))

app = QApplication([])
quit = False


def on_button_clicked():
    button.setEnabled(False)
    cfg = picam2.create_still_configuration()
    picam2.switch_mode_and_capture_file(cfg, "test.jpg", signal_function=qpicamera2.signal_done)


def capture_done(job):
    picam2.wait(job)
    button.setEnabled(True)


def app_quit():
    if quit:
        app.quit()


qpicamera2 = QGlPicamera2(picam2, width=800, height=600, keep_ar=False)
button = QPushButton("Click to capture JPEG")
label = QLabel()
window = QWidget()
qpicamera2.done_signal.connect(capture_done)
button.clicked.connect(on_button_clicked)

label.setFixedWidth(400)
label.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
layout_h = QHBoxLayout()
layout_v = QVBoxLayout()
layout_v.addWidget(label)
layout_v.addWidget(button)
layout_h.addWidget(qpicamera2, 80)
layout_h.addLayout(layout_v, 20)
window.setWindowTitle("Qt Picamera2 App")
window.resize(1200, 600)
window.setLayout(layout_h)
# Use timer as a hacky way to quit.
timer = QtCore.QTimer()
timer.timeout.connect(app_quit)
timer.start(500)

picam2.start()
window.show()


def test_func():
    global quit
    # This function can run in another thread and "click" on the GUI.
    time.sleep(5)
    button.clicked.emit()
    time.sleep(5)
    button.clicked.emit()
    time.sleep(5)
    # A rather nasty way of quitting. We can't call app.quit() from here in PyQt6.
    quit = True


thread = threading.Thread(target=test_func, daemon=True)
thread.start()

app.exec()
