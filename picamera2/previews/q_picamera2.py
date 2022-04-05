from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSlot, QSocketNotifier
from PyQt5.QtWidgets import QWidget, QApplication, QLabel
from PIL import Image
from PIL.ImageQt import ImageQt
import numpy as np


class QPiCamera2(QWidget):
    def __init__(self, picam2, parent=None, width=640, height=480):
        super().__init__(parent=parent)
        self.PiCamera2 = picam2
        self.label = QLabel(self)
        self.label.resize(width, height)
        self.overlay = None
        self.painter = QtGui.QPainter()
        self.camera_notifier = QSocketNotifier(self.PiCamera2.camera_manager.efd,
                                               QtCore.QSocketNotifier.Read,
                                               self)
        self.camera_notifier.activated.connect(self.handle_requests)

    def set_overlay(self, overlay):
        if overlay is not None:
            # Better to resize the overlay here rather than in the rendering loop.
            orig = overlay
            overlay = np.ascontiguousarray(overlay)
            shape = overlay.shape
            size = self.label.size()
            if orig is overlay and shape[1] == size.width() and shape[0] == size.height():
                # We must be sure to copy the data even when no one else does!
                overlay = overlay.copy()
            overlay = QtGui.QImage(overlay.data, shape[1], shape[0], QtGui.QImage.Format_RGBA8888)
            if overlay.size() != self.label.size():
                overlay = overlay.scaled(self.label.size())

        self.overlay = overlay

    @pyqtSlot()
    def handle_requests(self):
        request = self.PiCamera2.process_requests()
        if not request:
            return

        if self.PiCamera2.display_stream_name is not None:
            # This all seems horribly expensive. Pull request welcome if you know a better way!
            size = self.label.size()
            img = request.make_image(self.PiCamera2.display_stream_name, size.width(), size.height())
            qim = ImageQt(img)
            self.painter.begin(qim)
            overlay = self.overlay
            if overlay is not None:
                self.painter.drawImage(0, 0, overlay)
            self.painter.end()
            pix = QtGui.QPixmap.fromImage(qim)
            self.label.setPixmap(pix)
        request.release()
