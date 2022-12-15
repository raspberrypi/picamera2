#!/usr/bin/python3

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
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput
from picamera2.previews.qt import QGlPicamera2


def post_callback(request):
    label.setText(
        "".join("{}: {}\n".format(k, v) for k, v in request.get_metadata().items())
    )


picam2 = Picamera2()
picam2.post_callback = post_callback
picam2.configure(picam2.create_video_configuration(main={"size": (1280, 720)}))

app = QApplication([])


def on_button_clicked():
    global recording
    if not recording:
        encoder = H264Encoder(10000000)
        output = FileOutput("test.h264")
        picam2.start_encoder(encoder, output)
        button.setText("Stop recording")
        recording = True
    else:
        picam2.stop_encoder()
        button.setText("Start recording")
        recording = False


qpicamera2 = QGlPicamera2(picam2, width=800, height=480, keep_ar=False)
button = QPushButton("Start recording")
button.clicked.connect(on_button_clicked)
label = QLabel()
window = QWidget()
window.setWindowTitle("Qt Picamera2 App")
recording = False

label.setFixedWidth(400)
label.setAlignment(QtCore.Qt.AlignTop)
layout_h = QHBoxLayout()
layout_v = QVBoxLayout()
layout_v.addWidget(label)
layout_v.addWidget(button)
layout_h.addWidget(qpicamera2, 80)
layout_h.addLayout(layout_v, 20)
window.resize(1200, 480)
window.setLayout(layout_h)

picam2.start()
window.show()
app.exec()
