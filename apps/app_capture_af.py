#!/usr/bin/python3

from libcamera import controls
from PyQt5 import QtCore
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QLabel,
                             QPushButton, QVBoxLayout, QWidget)

from picamera2 import Picamera2
from picamera2.previews.qt import QGlPicamera2

STATE_AF = 0
STATE_CAPTURE = 1


def request_callback(request):
    label.setText(''.join(f"{k}: {v}\n" for k, v in request.get_metadata().items()))


picam2 = Picamera2()
picam2.post_callback = request_callback
# Adjust the preview size to match the sensor aspect ratio.
preview_width = 800
preview_height = picam2.sensor_resolution[1] * 800 // picam2.sensor_resolution[0]
preview_height -= preview_height % 2
preview_size = (preview_width, preview_height)
# We also want a full FoV raw mode, this gives us the 2x2 binned mode.
raw_size = tuple([v // 2 for v in picam2.camera_properties['PixelArraySize']])
preview_config = picam2.create_preview_configuration({"size": preview_size}, raw={"size": raw_size})
picam2.configure(preview_config)
if 'AfMode' not in picam2.camera_controls:
    print("Attached camera does not support autofocus")
    quit()
picam2.set_controls({"AfMode": controls.AfModeEnum.Auto})
app = QApplication([])


def on_button_clicked():
    global state
    button.setEnabled(False)
    continuous_checkbox.setEnabled(False)
    af_checkbox.setEnabled(False)
    state = STATE_AF if af_checkbox.isChecked() else STATE_CAPTURE
    if state == STATE_AF:
        picam2.autofocus_cycle(signal_function=qpicamera2.signal_done)
    else:
        do_capture()


def do_capture():
    cfg = picam2.create_still_configuration()
    picam2.switch_mode_and_capture_file(cfg, "test.jpg", signal_function=qpicamera2.signal_done)


def callback(job):
    global state
    if state == STATE_AF:
        state = STATE_CAPTURE
        success = "succeeded" if picam2.wait(job) else "failed"
        print(f"AF cycle {success} in {job.calls} frames")
        do_capture()
    else:
        picam2.wait(job)
        picam2.set_controls({"AfMode": controls.AfModeEnum.Auto})
        button.setEnabled(True)
        continuous_checkbox.setEnabled(True)
        af_checkbox.setEnabled(True)


def on_continuous_toggled(checked):
    mode = controls.AfModeEnum.Continuous if checked else controls.AfModeEnum.Auto
    picam2.set_controls({"AfMode": mode})


window = QWidget()
bg_colour = window.palette().color(QPalette.Background).getRgb()[:3]
qpicamera2 = QGlPicamera2(picam2, width=preview_width, height=preview_height, bg_colour=bg_colour)
qpicamera2.done_signal.connect(callback, type=QtCore.Qt.QueuedConnection)

button = QPushButton("Click to capture JPEG")
button.clicked.connect(on_button_clicked)
label = QLabel()
af_checkbox = QCheckBox("AF before capture", checked=False)
continuous_checkbox = QCheckBox("Continuous AF", checked=False)
continuous_checkbox.toggled.connect(on_continuous_toggled)
window.setWindowTitle("Qt Picamera2 App")

label.setFixedWidth(400)
label.setAlignment(QtCore.Qt.AlignTop)
layout_h = QHBoxLayout()
layout_v = QVBoxLayout()
layout_v.addWidget(label)
layout_v.addWidget(continuous_checkbox)
layout_v.addWidget(af_checkbox)
layout_v.addWidget(button)
layout_h.addWidget(qpicamera2, 80)
layout_h.addLayout(layout_v, 20)
window.resize(1200, preview_height + 80)
window.setLayout(layout_h)

picam2.start()
window.show()
app.exec()
picam2.stop()
