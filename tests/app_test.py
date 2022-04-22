#!/usr/bin/python3

# Start a Qt application, and use an asynchronous thread to "click" on the GUI.

import sys
import time
import threading

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import *

from picamera2.previews.q_gl_picamera2 import *
from picamera2.picamera2 import *


def request_callback(request):
    label.setText(''.join("{}: {}\n".format(k, v) for k, v in request.get_metadata().items()))


picam2 = Picamera2()
picam2.request_callback = request_callback
picam2.configure(picam2.preview_configuration(main={"size": (800, 600)}))

app = QApplication([])


def on_button_clicked():
    button.setEnabled(False)
    cfg = picam2.still_configuration()
    picam2.switch_mode_and_capture_file(cfg, "test.jpg", wait=False, signal_function=qpicamera2.signal_done)


def capture_done():
    button.setEnabled(True)


qpicamera2 = QGlPicamera2(picam2, width=800, height=600)
button = QPushButton("Click to capture JPEG")
label = QLabel()
window = QWidget()
qpicamera2.done_signal.connect(capture_done)
button.clicked.connect(on_button_clicked)

label.setFixedWidth(400)
label.setAlignment(QtCore.Qt.AlignTop)
layout_h = QHBoxLayout()
layout_v = QVBoxLayout()
layout_v.addWidget(label)
layout_v.addWidget(button)
layout_h.addWidget(qpicamera2, 80)
layout_h.addLayout(layout_v, 20)
window.setWindowTitle("Qt Picamera2 App")
window.resize(1200, 600)
window.setLayout(layout_h)

picam2.start()
window.show()


def test_func():
    # This function can run in another thread and "click" on the GUI.
    time.sleep(5)
    button.clicked.emit()
    time.sleep(5)
    button.clicked.emit()
    time.sleep(5)
    app.quit()


thread = threading.Thread(target=test_func, daemon=True)
thread.start()

app.exec()
