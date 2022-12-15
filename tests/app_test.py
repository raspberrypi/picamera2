#!/usr/bin/python3

# Start a Qt application, and use an asynchronous thread to "click" on the GUI.

import threading
import time

from PyQt5 import QtCore
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from picamera2 import Picamera2
from picamera2.previews.qt import QGlPicamera2


def post_callback(request):
    label.setText(
        "".join("{}: {}\n".format(k, v) for k, v in request.get_metadata().items())
    )


Picamera2.set_logging()
picam2 = Picamera2()
picam2.post_callback = post_callback
picam2.configure(picam2.create_preview_configuration(main={"size": (800, 600)}))

app = QApplication([])


def on_button_clicked():
    button.setEnabled(False)
    cfg = picam2.create_still_configuration()
    picam2.switch_mode_and_capture_file(
        cfg, "test.jpg", signal_function=qpicamera2.signal_done
    )


def capture_done(job):
    picam2.wait(job)
    button.setEnabled(True)


qpicamera2 = QGlPicamera2(picam2, width=800, height=600, keep_ar=False)
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
