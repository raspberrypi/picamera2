#!/usr/bin/python3

# This example is similar to the app_capture2.py example, however here we
# capture a request. The request is returned to us in the picamera2's
# async_result field.

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
from picamera2.previews.qt import QPicamera2


def post_callback(request):
    label.setText(
        "".join("{}: {}\n".format(k, v) for k, v in request.get_metadata().items())
    )


picam2 = Picamera2()
picam2.post_callback = post_callback
picam2.configure(picam2.create_preview_configuration(main={"size": (800, 600)}))

app = QApplication([])


def on_button_clicked():
    button.setEnabled(False)
    picam2.capture_request(wait=False, signal_function=qpicamera2.signal_done)


def capture_done(job):
    # Here's the request we captured. But we must always release it when we're done with it!
    request = picam2.wait(job)
    print("Request:", request)
    request.release()
    button.setEnabled(True)


qpicamera2 = QPicamera2(picam2, width=800, height=600)
button = QPushButton("Click to capture")
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
app.exec()
