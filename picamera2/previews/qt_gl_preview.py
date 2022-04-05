import PiCamera2.PiCamera2
import threading
import atexit


class QtGlPreview:
    def thread_func(self, picam2, width, height):
        # Running Qt in a thread other than the main thread is a bit tricky...
        from PiCamera2.previews.q_gl_PiCamera2 import QApplication, QGlPiCamera2

        self.app = QApplication([])
        self.size = (width, height)
        self.qPiCamera2 = QGlPiCamera2(picam2, width=width, height=height)
        self.qPiCamera2.setWindowTitle("QtGlPreview")
        self.qPiCamera2.show()
        picam2.asynchronous = True
        # Can't get Qt to exit tidily without this. Possibly an artifact of running
        # it in another thread?
        atexit.register(self.stop)
        self.event.set()

        self.app.exec()

        atexit.unregister(self.stop)
        self.qPiCamera2.PiCamera2.asynchronous = False
        # Again, all necessary to keep Qt quiet.
        del self.qPiCamera2
        del self.app

    def __init__(self, width=640, height=480):
        self.width = width
        self.height = height

    def start(self, picam2):
        self.event = threading.Event()
        self.thread = threading.Thread(target=self.thread_func,
                                       args=(picam2, self.width, self.height))
        self.thread.setDaemon(True)
        self.thread.start()
        self.event.wait()

    def stop(self):
        if hasattr(self, "app"):
            self.app.quit()
        self.thread.join()

    def set_overlay(self, overlay):
        self.qPiCamera2.set_overlay(overlay)
