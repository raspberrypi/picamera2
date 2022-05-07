from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, pyqtSlot, pyqtSignal, QSocketNotifier, QSize
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene
import numpy as np


class QPicamera2(QGraphicsView):
    update_overlay_signal = pyqtSignal()

    def __init__(self, picam2, parent=None, width=640, height=480):
        super().__init__(parent=parent)
        self.picamera2 = picam2
        self.size = QSize(width, height)
        self.pixmap = None
        self.new_pixmap = None
        self.overlay = None
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.resize(width, height)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.enabled = True

        self.update_overlay_signal.connect(self.update_overlay)
        self.camera_notifier = QSocketNotifier(self.picamera2.camera_manager.efd,
                                               QtCore.QSocketNotifier.Read,
                                               self)
        self.camera_notifier.activated.connect(self.handle_requests)

    def cleanup(self):
        del self.scene
        del self.new_pixmap
        del self.overlay
        del self.camera_notifier

    def signal_done(self, picamera2):
        self.done_signal.emit()

    def set_overlay(self, overlay):
        if overlay is not None:
            overlay = np.ascontiguousarray(overlay)
            shape = overlay.shape
            qim = QtGui.QImage(overlay.data, shape[1], shape[0],
                               QtGui.QImage.Format_RGBA8888)
            if qim.size() != self.size:
                # Resize the overlay
                qim = qim.scaled(self.size)
            self.new_pixmap = QtGui.QPixmap(qim)
        elif self.overlay is not None:
            # Remove overlay
            self.new_pixmap = None
        # Update the overlay. Really I want to pass the new_pixmap to the signal but can't
        # get that to work.
        self.update_overlay_signal.emit()

    @pyqtSlot()
    def update_overlay(self):
        pix = self.new_pixmap
        if pix is None:
            # Delete overlay if present
            if self.overlay is not None:
                self.scene.removeItem(self.overlay)
                self.overlay = None
        elif self.overlay is None:
            # Need to add the overlay to the scene
            self.overlay = self.scene.addPixmap(pix)
            self.overlay.setZValue(100)
        else:
            # Just update it
            self.overlay.setPixmap(pix)

    @pyqtSlot(bool)
    def set_enabled(self, enabled):
        self.enabled = enabled

    def fitInView(self):
        # Reimplemented fitInView to remove fixed border
        if self.pixmap is not None:
            rect = QtCore.QRectF(self.pixmap.pixmap().rect())
            self.setSceneRect(rect)
            unity = self.transform().mapRect(QtCore.QRectF(0, 0, 1, 1))
            self.scale(1 / unity.width(), 1 / unity.height())
            viewrect = self.viewport().rect()
            scenerect = self.transform().mapRect(rect)
            factor = min(viewrect.width() / scenerect.width(),
                            viewrect.height() / scenerect.height())
            self.scale(factor, factor)

    def resizeEvent(self, event):
        self.fitInView()
        QGraphicsView.resizeEvent(self, event)

    @pyqtSlot()
    def handle_requests(self):
        request = self.picamera2.process_requests()
        if not request:
            return

        if self.enabled and self.picamera2.display_stream_name is not None:
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
                self.fitInView()
            else:
                # Update pixmap
                self.pixmap.setPixmap(pix)
        request.release()
