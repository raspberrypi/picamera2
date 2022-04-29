from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, pyqtSlot, QSocketNotifier, QRect, QSize
from PyQt5.QtWidgets import QWidget, QApplication, QLabel
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene
import numpy as np


class QPicamera2(QGraphicsView):
    def __init__(self, picam2, parent=None, width=640, height=480):
        super().__init__(parent=parent)
        self.picamera2 = picam2
        self.size = QSize(width, height)
        self.pixmap = None
        self.overlay = None
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.resize(width, height)

        self.camera_notifier = QSocketNotifier(self.picamera2.camera_manager.efd,
                                               QtCore.QSocketNotifier.Read,
                                               self)
        self.camera_notifier.activated.connect(self.handle_requests)

    def set_overlay(self, overlay):
        if overlay is not None:
            overlay = np.ascontiguousarray(overlay)
            shape = overlay.shape
            qim = QtGui.QImage(overlay.data, shape[1], shape[0],
                               QtGui.QImage.Format_RGBA8888)
            if qim.size() != self.size:
                # Resize the overlay
                qim = qim.scaled(self.size)
            pix = QtGui.QPixmap(qim)
            if self.overlay is None:
                # Need to add the overlay to the scene
                self.overlay = self.scene.addPixmap(pix)
                self.overlay.setZValue(100)
            else:
                # Just update it
                self.overlay.setPixmap(pix)
        elif self.overlay is not None:
            # Remove overlay
            self.scene.removeItem(self.overlay)
            self.overlay = None

    @pyqtSlot()
    def handle_requests(self):
        request = self.picamera2.process_requests()
        if not request:
            return

        if self.picamera2.display_stream_name is not None:
            img = request.make_array(self.picamera2.display_stream_name)
            img = np.ascontiguousarray(img[..., :3])
            shape = img.shape
            qim = QtGui.QImage(img.data, shape[1], shape[0],
                               QtGui.QImage.Format_RGB888)
            if qim.size() != self.size:
                # Make the qim match the size of the scene if necessary.
                # Sometimes changing to a different configuration provides
                # a larger image to the request, increasing the scene size.
                qim = qim.scaled(self.size)
            pix = QtGui.QPixmap(qim)
            if self.pixmap is None:
                # Add the pixmap to the scene
                self.pixmap = self.scene.addPixmap(pix)
            else:
                # Update pixmap
                self.pixmap.setPixmap(pix)
            self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)
        request.release()
