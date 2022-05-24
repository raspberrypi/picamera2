from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSlot, QSocketNotifier, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPixmap, QImage
from PyQt5.QtWidgets import QWidget, QApplication, QLabel
from PIL import Image
from PIL.ImageQt import ImageQt
import numpy as np


class QPicamera2(QWidget):
    done_signal = pyqtSignal()
    update_overlay_signal = pyqtSignal(object)

    def __init__(self, picam2, parent=None, width=640, height=480, bg_colour=(20, 20, 20), keep_ar=True):
        super().__init__(parent=parent)
        self.picamera2 = picam2
        picam2.have_event_loop = True
        self.bg_colour = bg_colour
        self.keep_ar = keep_ar
        self.pil_img = None
        self.pil_img_resized = None
        self.label = QLabel(self)
        self.label.resize(width, height)
        self.overlay = None
        self.overlay_resized = None
        self.painter = QPainter()
        self.update_overlay_signal.connect(self.update_overlay)
        self.camera_notifier = QSocketNotifier(self.picamera2.camera_manager.efd,
                                               QSocketNotifier.Read, self)
        self.camera_notifier.activated.connect(self.handle_requests)

    def cleanup(self):
        del self.label
        del self.camera_notifier

    def signal_done(self, picamera2):
        self.done_signal.emit()

    def set_overlay(self, overlay):
        if overlay is not None:
            overlay = np.copy(overlay, order='C')
            shape = overlay.shape
            overlay = QImage(overlay.data, shape[1], shape[0], QImage.Format_RGBA8888)
        self.update_overlay_signal.emit(overlay)

    def update_overlay(self, overlay):
        self.overlay = overlay
        self.overlay_resized = None
        self.update()

    def recalculate_viewport(self):
        size = self.label.size()
        win_w = size.width()
        win_h = size.height()

        stream_map = self.picamera2.stream_map
        camera_config = self.picamera2.camera_config
        if not self.keep_ar or camera_config is None or camera_config['display'] is None:
            return 0, 0, win_w, win_h

        im_w, im_h = stream_map[camera_config['display']].configuration.size
        if im_w * win_h > win_w * im_h:
            im_win_w = win_w
            im_win_h = win_w * im_h // im_w
        else:
            im_win_h = win_h
            im_win_w = win_h * im_w // im_h
        im_win_x = (win_w - im_win_w) // 2
        im_win_y = (win_h - im_win_h) // 2
        return (im_win_x, im_win_y, im_win_w, im_win_h)

    def paintEvent(self, event):
        # This all seems horribly expensive. Pull request welcome if you know a better way!
        picam2 = self.picamera2
        size = self.label.size()
        win_w = size.width()
        win_h = size.height()
        im_win_x, im_win_y, im_win_w, im_win_h = self.recalculate_viewport()

        # Check if the pil_img needs to be resized again if the window has changed.
        if self.pil_img_resized:
            if self.pil_img_resized.width != im_win_w or self.pil_img_resized.height != im_win_h:
                self.pil_img_resized = None

        # Remake the cached version that fits in the window.
        if self.pil_img_resized is None and self.pil_img:
            if self.pil_img.width == im_win_w and self.pil_img.height == im_win_h:
                self.pil_img_resized = self.pil_img
            else:
                self.pil_img_resized = self.pil_img.resize((im_win_w, im_win_h))

        # The cached resized overlay needs to be resized again if the window has changed.
        if self.overlay_resized:
            if self.overlay_resized.width() != im_win_w or self.overlay_resized.height() != im_win_h:
                self.overlay_resized = None

        # Remake the cached resized overlay.
        if self.overlay and self.overlay_resized is None:
            self.overlay_resized = self.overlay.scaled(im_win_w, im_win_h)

        # Now render everything onto the label.
        pixmap = QPixmap(win_w, win_h)
        self.painter.begin(pixmap)
        self.painter.fillRect(0, 0, win_w, win_h, QColor.fromRgb(*self.bg_colour))

        if self.pil_img_resized:
            self.painter.drawImage(im_win_x, im_win_y, ImageQt(self.pil_img_resized))

        if self.overlay_resized:
            self.painter.drawImage(im_win_x, im_win_y, self.overlay_resized)

        self.painter.end()
        self.label.setPixmap(pixmap)

    def resizeEvent(self, event):
        self.label.resize(self.width(), self.height())
        self.update()

    @pyqtSlot()
    def handle_requests(self):
        request = self.picamera2.process_requests()
        if not request:
            return

        self.pil_img = None
        self.pil_img_resized = None
        if self.picamera2.display_stream_name is not None:
            self.pil_img = request.make_image(self.picamera2.display_stream_name)

        request.release()
        self.update()
