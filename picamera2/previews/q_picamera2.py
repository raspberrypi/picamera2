import logging

import numpy as np
from libcamera import Transform
from PyQt5.QtCore import (QRect, QRectF, QSize, QSocketNotifier, Qt,
                          pyqtSignal, pyqtSlot)
from PyQt5.QtGui import QBrush, QColor, QImage, QPixmap, QTransform
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsView

try:
    import cv2
    cv2_available = True
except ImportError:
    cv2_available = False


class QPicamera2(QGraphicsView):
    done_signal = pyqtSignal(object)
    update_overlay_signal = pyqtSignal(object)

    def __init__(self, picam2, parent=None, width=640, height=480, bg_colour=(20, 20, 20),
                 keep_ar=True, transform=None, preview_window=None):
        super().__init__(parent=parent)
        self.picamera2 = picam2
        picam2.attach_preview(preview_window)
        self.preview_window = preview_window
        self.keep_ar = keep_ar
        self.transform = Transform() if transform is None else transform
        self.image_size = None
        self.last_rect = QRect(0, 0, 0, 0)

        self.size = QSize(width, height)
        self.pixmap = None
        self.overlay = None
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setBackgroundBrush(QBrush(QColor(*bg_colour)))
        self.resize(width, height)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.enabled = True
        self.title_function = None

        self.update_overlay_signal.connect(self.update_overlay)
        self.camera_notifier = QSocketNotifier(self.picamera2.notifyme_r,
                                               QSocketNotifier.Read, self)
        self.camera_notifier.activated.connect(self.handle_requests)
        # Must always run cleanup when this widget goes away.
        self.destroyed.connect(lambda: self.cleanup())
        self.running = True

    def cleanup(self):
        if not self.running:
            return
        self.running = False
        del self.scene
        del self.overlay
        self.camera_notifier.deleteLater()
        # We have to tell both the preview window and the Picamera2 object that we have
        # disappeared.
        self.picamera2.detach_preview()
        if self.preview_window is not None:  # will be none when a proper Qt app
            self.preview_window.qpicamera2 = None

    def closeEvent(self, event):
        self.cleanup()

    def signal_done(self, job):
        self.done_signal.emit(job)

    def image_dimensions(self):
        # The dimensions of the camera images we're displaying.
        camera_config = self.picamera2.camera_config
        if camera_config is not None and camera_config['display'] is not None:
            # This works even before we receive any camera images.
            size = (self.picamera2.stream_map[camera_config['display']].configuration.size.width,
                    self.picamera2.stream_map[camera_config['display']].configuration.size.height)
        elif self.image_size is not None:
            # If the camera is unconfigured, stick with the last size (if available).
            size = self.image_size
        else:
            # Otherwise pretend the image fills everything.
            rect = self.viewport().rect()
            size = rect.width(), rect.height()
        self.image_size = size
        return size

    def set_overlay(self, overlay):
        camera_config = self.picamera2.camera_config
        if camera_config is None:
            raise RuntimeError("Camera must be configured before using set_overlay")

        new_pixmap = None
        if overlay is not None:
            overlay = np.copy(overlay, order='C')
            shape = overlay.shape
            qim = QImage(overlay.data, shape[1], shape[0], QImage.Format_RGBA8888)
            new_pixmap = QPixmap(qim)
            # No scaling here - we leave it to fitInView to set that up.
        self.update_overlay_signal.emit(new_pixmap)

    @pyqtSlot(object)
    def update_overlay(self, pix):
        if pix is None:
            # Delete overlay if present
            if self.overlay is not None:
                self.scene.removeItem(self.overlay)
                self.overlay = None
                return
        elif self.overlay is None:
            # Need to add the overlay to the scene
            self.overlay = self.scene.addPixmap(pix)
            self.overlay.setZValue(100)
        else:
            # Just update it
            self.overlay.setPixmap(pix)
        self.fitInView()

    @pyqtSlot(bool)
    def set_enabled(self, enabled):
        self.enabled = enabled

    def fitInView(self):
        # Reimplemented fitInView to remove fixed border
        image_w, image_h = self.image_dimensions()
        rect = QRectF(0, 0, image_w, image_h)
        self.setSceneRect(rect)
        # I get one column of background peeping through on the right without this:
        viewrect = self.viewport().rect().adjusted(0, 0, 1, 1)
        self.resetTransform()
        factor_x = viewrect.width() / image_w
        factor_y = viewrect.height() / image_h
        if self.keep_ar:
            factor_x = min(factor_x, factor_y)
            factor_y = factor_x
        if self.transform.hflip:
            factor_x = -factor_x
        if self.transform.vflip:
            factor_y = -factor_y
        self.scale(factor_x, factor_y)

        # This scales the overlay to be on top of the camera image.
        if self.overlay:
            rect = self.overlay.boundingRect()
            self.overlay.resetTransform()
            factor_x = image_w / rect.width()
            factor_y = image_h / rect.height()
            translate_x, translate_y = 0, 0
            if self.transform.hflip:
                factor_x = -factor_x
                translate_x = -rect.width()
            if self.transform.vflip:
                factor_y = -factor_y
                translate_y = -rect.height()
            transform = QTransform.fromScale(factor_x, factor_y)
            transform.translate(translate_x, translate_y)
            self.overlay.setTransform(transform, True)

    def resizeEvent(self, event):
        self.fitInView()

    def render_request(self, completed_request):
        """Draw the camera image using Qt."""
        if not self.enabled:
            return

        if self.title_function is not None:
            self.setWindowTitle(self.title_function(completed_request.get_metadata()))

        camera_config = completed_request.config
        display_stream_name = camera_config['display']
        stream_config = camera_config[display_stream_name]

        img = completed_request.make_array(display_stream_name)
        if stream_config["format"] in ("YUV420", "YUYV"):
            if cv2_available:
                if stream_config["format"] == "YUV420":
                    img = cv2.cvtColor(img, cv2.COLOR_YUV420p2BGR)
                else:
                    img = cv2.cvtColor(img, cv2.COLOR_YUV2RGB_YUYV)
            else:
                logging.error("Qt preview cannot display YUV420/YUYV without cv2")
                return

        # Crop width for two reasons: (1) to remove "stride" padding from YUV images;
        # (2) to ensure the RGB buffer passed to QImage has mandatory 4-byte alignment.
        # [TODO: Consider QImage.Format_RGB32, if byte order can be made correct]
        width = min(img.shape[1], stream_config["size"][0])
        width -= width % 4
        img = np.ascontiguousarray(img[:, :width, :3])
        fmt = QImage.Format_BGR888 if stream_config['format'] in ('RGB888', 'XRGB8888') else QImage.Format_RGB888
        qim = QImage(img.data, width, img.shape[0], fmt)
        pix = QPixmap(qim)
        # Add the pixmap to the scene if there wasn't one, or replace it if the images have
        # changed size.
        if self.pixmap is None or pix.rect() != self.last_rect:
            if self.pixmap:
                self.scene.removeItem(self.pixmap)
            self.last_rect = pix.rect()
            self.pixmap = self.scene.addPixmap(pix)
            self.fitInView()
        else:
            # Update pixmap
            self.pixmap.setPixmap(pix)

    @pyqtSlot()
    def handle_requests(self):
        if not self.running:
            return
        self.picamera2.notifymeread.read()
        self.picamera2.process_requests(self)
