import atexit
import os
import threading
from enum import Enum
from queue import Queue


class Command(Enum):
    CREATE = 1
    DELETE = 2
    FIN = 3


class QtPreviewBase:
    thread = None

    def make_picamera2_widget(picam2, width=640, height=480, transform=None):
        pass

    def get_title():
        pass

    def thread_func(self, previewcreateq):
        # Running Qt in a thread other than the main thread is a bit tricky...
        from PyQt5 import QtCore
        from PyQt5.QtWidgets import QApplication

        @QtCore.pyqtSlot()
        def deletepreview(parent, preview, previewretrieveq):
            preview.hide()
            preview.cleanup()
            atexit.unregister(parent.stop)
            previewretrieveq.put(0)

        @QtCore.pyqtSlot()
        def createpreview(parent, cam, previewretrieveq):
            qpicamera2 = parent.make_picamera2_widget(
                cam, width=parent.width, height=parent.height, transform=parent.transform
            )
            if parent.x is not None and parent.y is not None:
                qpicamera2.move(parent.x, parent.y)
            qpicamera2.setWindowTitle(parent.get_title())
            qpicamera2.show()
            atexit.register(parent.stop)
            previewretrieveq.put(qpicamera2)

        class MonitorThread(QtCore.QThread):
            previewsignal = QtCore.pyqtSignal(object, object, object)
            deletesignal = QtCore.pyqtSignal(object, object, object)

            def __init__(self, previewcreateq, app):
                super(MonitorThread, self).__init__()
                self.previewcreateq = previewcreateq
                self.app = app

            def run(self):
                from PyQt5.QtGui import QGuiApplication

                # This ensures the Qt app never quits when we click the X on the window. It means
                # that after closing the last preview in this way, the Qt app is still running and
                # you can create new previews.
                QGuiApplication.setQuitOnLastWindowClosed(False)

                while True:
                    cmd, retq, tup = self.previewcreateq.get()
                    if cmd == Command.CREATE:
                        parent, cam = tup
                        self.previewsignal.emit(parent, cam, retq)
                    elif cmd == Command.DELETE:
                        parent, preview = tup
                        self.deletesignal.emit(parent, preview, retq)
                        parent = preview = tup = None
                    elif cmd == Command.FIN:
                        self.app.quit()
                        break

        app = QApplication([])
        # Can't get Qt to exit tidily without this. Possibly an artifact of running
        # it in another thread?
        monitor = MonitorThread(previewcreateq, app)
        monitor.previewsignal.connect(createpreview)
        monitor.deletesignal.connect(deletepreview)
        monitor.start()
        self.event.set()
        atexit.register(self.fin)
        app.exec()
        monitor.wait()
        atexit.unregister(self.fin)
        del app
        # Again, all necessary to keep Qt quiet.

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
            QtPreviewBase.thread = threading.Thread(target=self.thread_func, args=(QtPreviewBase.previewcreateq,))
            QtPreviewBase.thread.setDaemon(True)
            QtPreviewBase.thread.start()
            self.event.wait()
        retq = Queue()
        QtPreviewBase.previewcreateq.put((Command.CREATE, retq, (self, picam2)))
        self.qpicamera2 = retq.get()

    def stop(self):
        if self.qpicamera2:
            retq = Queue()
            QtPreviewBase.previewcreateq.put((Command.DELETE, retq, (self, self.qpicamera2)))
            retq.get()

    def fin(self):
        if QtPreviewBase.thread:
            QtPreviewBase.previewcreateq.put((Command.FIN, None, None))
            QtPreviewBase.thread.join()
            QtPreviewBase.thread = None

    def set_overlay(self, overlay):
        self.qpicamera2.set_overlay(overlay)

    def set_title_function(self, function):
        self.qpicamera2.title_function = function


class QtPreview(QtPreviewBase):
    def make_picamera2_widget(self, picam2, width=640, height=480, transform=None):
        from picamera2.previews.qt import QPicamera2

        return QPicamera2(picam2, width=self.width, height=self.height, transform=self.transform, preview_window=self)

    def get_title(self):
        return "QtPreview"


class QtGlPreview(QtPreviewBase):
    def start(self, picam2):
        # Set QT_QPA_PLATFORM before QApplication is created (only on first
        # preview, only when the user hasn't already set it explicitly).
        if QtPreviewBase.thread is None and 'QT_QPA_PLATFORM' not in os.environ:
            if os.environ.get('WAYLAND_DISPLAY'):
                os.environ['QT_QPA_PLATFORM'] = 'wayland'
            else:
                os.environ['QT_QPA_PLATFORM'] = 'xcb'
        super().start(picam2)

    def make_picamera2_widget(self, picam2, width=640, height=480, transform=None):
        from picamera2.previews.qt import QGlPicamera2

        return QGlPicamera2(picam2, width=self.width, height=self.height, transform=self.transform, preview_window=self)

    def get_title(self):
        return "QtGlPreview"


class QtGlPreviewWayland(QtPreviewBase):
    # Kept for backward compatibility; Preview.QTGL now auto-detects the
    # platform.  This class still works and explicitly requests the Wayland path
    # when a compositor is available.
    def start(self, picam2):
        if QtPreviewBase.thread is None and 'QT_QPA_PLATFORM' not in os.environ:
            if os.environ.get('WAYLAND_DISPLAY'):
                os.environ['QT_QPA_PLATFORM'] = 'wayland'
        super().start(picam2)

    def make_picamera2_widget(self, picam2, width=640, height=480, transform=None):
        from picamera2.previews.qt import QGlPicamera2

        return QGlPicamera2(picam2, width=self.width, height=self.height, transform=self.transform, preview_window=self)

    def get_title(self):
        return "QtGlPreviewWayland"


class QtGlPreviewDirect(QtGlPreview):
    # Like QtGlPreview but requests the direct QOpenGLWindow renderer on
    # Wayland (no FBO blit); on X11 falls back to the standard QtGlPreview
    # path.  See the stacking caveats in q_gl_picamera2_wl_direct.py.
    def make_picamera2_widget(self, picam2, width=640, height=480, transform=None):
        from picamera2.previews.qt import QGlPicamera2

        return QGlPicamera2(
            picam2, direct=True, width=self.width, height=self.height, transform=self.transform, preview_window=self
        )

    def get_title(self):
        return "QtGlPreviewDirect"


# Kept for any code that references these classes directly; the Preview enum
# no longer exposes them.
QtGlPreviewWaylandDirect = QtGlPreviewDirect
