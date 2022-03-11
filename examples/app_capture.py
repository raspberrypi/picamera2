#!/usr/bin/python3

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
    if not picam2.async_operation_in_progress:
        cfg = picam2.still_configuration()
        picam2.switch_mode_and_capture_file(cfg, "test.jpg", wait=False, signal_function=None)
    else:
        print("Busy!")

qpicamera2 = QGlPicamera2(picam2, width=800, height=600)
button = QPushButton("Click to capture JPEG")
button.clicked.connect(on_button_clicked)
label = QLabel()
window = QWidget()
window.setWindowTitle("Qt Picamera2 App")

label.setFixedWidth(400)
label.setAlignment(QtCore.Qt.AlignTop)
layout_h = QHBoxLayout()
layout_v = QVBoxLayout()
layout_v.addWidget(label)
layout_v.addWidget(button)
layout_h.addWidget(qpicamera2, 80)
layout_h.addLayout(layout_v, 20)
window.resize(1200, 600)
window.setLayout(layout_h)

picam2.start()
window.show()
app.exec()
