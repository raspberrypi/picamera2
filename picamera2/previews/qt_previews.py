import atexit
import threading

import picamera2.picamera2


class QtPreviewBase:
    def make_picamera2_widget(picam2, width=640, height=480, transform=None):
        pass

    def get_title():
        pass

    def thread_func(self, picam2):
        # Running Qt in a thread other than the main thread is a bit tricky...
        from PyQt5 import QtCore
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QApplication

        self.app = QApplication([])
        self.size = (self.width, self.height)
        self.qpicamera2 = self.make_picamera2_widget(picam2, width=self.width, height=self.height, transform=self.transform)
        if self.x is not None and self.y is not None:
            self.qpicamera2.move(self.x, self.y)
        self.qpicamera2.setWindowTitle(self.get_title())
        self.qpicamera2.show()
        # Can't get Qt to exit tidily without this. Possibly an artifact of running
        # it in another thread?
        atexit.register(self.stop)
        self.event.set()

        self.app.exec()

        atexit.unregister(self.stop)
        # Again, all necessary to keep Qt quiet.
        self.qpicamera2.cleanup()
        del self.qpicamera2
        del self.app

    def __init__(self, x=None, y=None, width=640, height=480, transform=None):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.transform = transform

    def start(self, picam2):
        self.event = threading.Event()
        self.thread = threading.Thread(target=self.thread_func, args=(picam2, ))
        self.thread.setDaemon(True)
        self.thread.start()
        self.event.wait()

    def stop(self):
        if hasattr(self, "app"):
            self.app.quit()
        self.thread.join()

    def set_overlay(self, overlay):
        self.qpicamera2.set_overlay(overlay)


class QtPreview(QtPreviewBase):
    def make_picamera2_widget(self, picam2, width=640, height=480, transform=None):
        from picamera2.previews.qt import QPicamera2
        return QPicamera2(picam2, width=self.width, height=self.height, transform=self.transform)

    def get_title(self):
        return "QtPreview"


class QtGlPreview(QtPreviewBase):
    def make_picamera2_widget(self, picam2, width=640, height=480, transform=None):
        from picamera2.previews.qt import QGlPicamera2
        return QGlPicamera2(picam2, width=self.width, height=self.height, transform=self.transform)

    def get_title(self):
        return "QtGlPreview"
