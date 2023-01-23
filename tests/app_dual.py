#!/usr/bin/python3

# Show how you can run two camera previews in the same Qt app.

import time
from threading import Thread

from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QPushButton,
                             QVBoxLayout, QWidget)

from picamera2 import Picamera2
from picamera2.previews.qt import QGlPicamera2, QPicamera2

if len(Picamera2.global_camera_info()) <= 1:
    print("SKIPPED (one camera)")
    quit()

picams = [Picamera2(0), Picamera2(1)]
picams[0].configure(picams[0].create_preview_configuration(main={"size": (800, 600)}))
picams[1].configure(picams[1].create_preview_configuration(main={"size": (800, 600)}))

app = QApplication([])
requests = []


def on_button_clicked():
    button.setEnabled(False)
    picams[0].capture_request(wait=False, signal_function=qpicameras[0].signal_done)
    picams[1].capture_request(wait=False, signal_function=qpicameras[1].signal_done)


def capture_done(job):
    global requests
    request = job.get_result()
    requests.append(request)
    if len(requests) == 2:
        print("Requests are", requests)
        requests[0].release()
        requests[1].release()
        requests = []
        button.setEnabled(True)


# Cam 1 gets a non-GL preview, in case it's a USB webcam.
qpicameras = [QGlPicamera2(picams[0], width=800, height=600), QPicamera2(picams[1], width=800, height=600)]
button = QPushButton("Click to capture")
window = QWidget()
qpicameras[0].done_signal.connect(capture_done)
qpicameras[1].done_signal.connect(capture_done)
button.clicked.connect(on_button_clicked)

layout_h = QHBoxLayout()
layout_v = QVBoxLayout()
layout_h.addWidget(qpicameras[0], 50)
layout_h.addWidget(qpicameras[1], 50)
layout_v.addLayout(layout_h)
layout_v.addWidget(button)
window.setWindowTitle("Qt Picamera2 App")
window.resize(1200, 500)
window.setLayout(layout_v)

picams[0].start()
picams[1].start()
window.show()


def test_func():
    # "Poke" the GUI to do a capture then quit.
    time.sleep(5)
    button.clicked.emit()
    time.sleep(5)
    app.quit()


thread = Thread(target=test_func, daemon=True)
thread.start()

app.exec()
