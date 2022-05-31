#!/usr/bin/python3

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QLabel, QHBoxLayout, QPushButton, QVBoxLayout, QApplication, QWidget, QCheckBox
import numpy as np

from picamera2.previews.qt import QPicamera2, QGlPicamera2
from picamera2 import Picamera2


def request_callback(request):
    label.setText(''.join("{}: {}\n".format(k, v)
                          for k, v in request.get_metadata().items()))


def cleanup():
    picam2.post_callback = None


picam2 = Picamera2()
picam2.post_callback = request_callback
picam2.configure(picam2.preview_configuration(main={"size": (800, 600)}))
app = QApplication([])


def on_button_clicked():
    if not picam2.async_operation_in_progress:
        cfg = picam2.still_configuration()
        picam2.switch_mode_and_capture_file(cfg, "test.jpg", wait=False,
                                            signal_function=None)
    else:
        print("Busy!")


overlay = np.zeros((300, 400, 4), dtype=np.uint8)
overlay[:150, 200:] = (255, 0, 0, 64)
overlay[150:, :200] = (0, 255, 0, 64)
overlay[150:, 200:] = (0, 0, 255, 64)


def on_checkbox_toggled(checked):
    if checked:
        qpicamera2.set_overlay(overlay)
    else:
        qpicamera2.set_overlay(None)


# Either camera widget implementation should work:
# qpicamera2 = QPicamera2(picam2, width=800, height=600)
# or:
qpicamera2 = QGlPicamera2(picam2, width=800, height=600)

button = QPushButton("Click to capture JPEG")
button.clicked.connect(on_button_clicked)
label = QLabel()
checkbox = QCheckBox("Set Overlay", checked=False)
checkbox.toggled.connect(on_checkbox_toggled)
window = QWidget()
window.setWindowTitle("Qt Picamera2 App")

label.setFixedWidth(400)
label.setAlignment(QtCore.Qt.AlignTop)
layout_h = QHBoxLayout()
layout_v = QVBoxLayout()
layout_v.addWidget(label)
layout_v.addWidget(checkbox)
layout_v.addWidget(button)
layout_h.addWidget(qpicamera2, 80)
layout_h.addLayout(layout_v, 20)
window.resize(1200, 600)
window.setLayout(layout_h)

picam2.start()
window.show()
app.exec()
picam2.stop()
