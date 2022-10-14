import atexit
import threading
from queue import Queue

import picamera2.picamera2


class QtPreviewBase:
    thread = None

    def make_picamera2_widget(picam2, width=640, height=480, transform=None):
        pass

    def get_title():
        pass

    def thread_func(self, previewcreateq, previewretrieveq):
        # Running Qt in a thread other than the main thread is a bit tricky...
        from PyQt5 import QtCore
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QApplication

        @QtCore.pyqtSlot(object, object, object)
        def createpreview(parent, cam, previewretrieveq):
            qpicamera2 = parent.make_picamera2_widget(cam, width=parent.width, height=parent.height,
                                                      transform=parent.transform)
            if parent.x is not None and parent.y is not None:
                qpicamera2.move(parent.x, parent.y)
            qpicamera2.setWindowTitle(parent.get_title())
            qpicamera2.show()
            previewretrieveq.put(qpicamera2)

        class MonitorThread(QtCore.QThread):

            previewsignal = QtCore.pyqtSignal(object, object, object)

            def __init__(self, previewcreateq, previewretrieveq):
                super(MonitorThread, self).__init__()
                self.previewcreateq = previewcreateq
                self.previewretrieveq = previewretrieveq

            def run(self):
                while True:
                    parent, cam = self.previewcreateq.get()
                    self.previewsignal.emit(parent, cam, self.previewretrieveq)

        self.app = QApplication([])
        # Can't get Qt to exit tidily without this. Possibly an artifact of running
        # it in another thread?
        atexit.register(self.stop)
        self.event.set()

        monitor = MonitorThread(previewcreateq, previewretrieveq)
        monitor.previewsignal.connect(createpreview)
        monitor.start()
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
        if QtPreviewBase.thread is None:
            QtPreviewBase.previewcreateq = Queue()
            QtPreviewBase.previewretrieveq = Queue()
            QtPreviewBase.thread = threading.Thread(target=self.thread_func, args=(QtPreviewBase.previewcreateq,
                                                    QtPreviewBase.previewretrieveq))
            QtPreviewBase.thread.setDaemon(True)
            QtPreviewBase.thread.start()
            self.event.wait()
        QtPreviewBase.previewcreateq.put((self, picam2))
        self.qpicamera2 = QtPreviewBase.previewretrieveq.get()

    def stop(self):
        if hasattr(self, "app"):
            self.app.quit()
        QtPreviewBase.thread.join()
        QtPreviewBase.thread = None

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
