import picamera2.picamera2
import threading
import atexit


class QtPreview:
    def thread_func(self, picam2, width, height):
        # Running Qt in a thread other than the main thread is a bit tricky...
        from picamera2.previews.q_picamera2 import QApplication, QPicamera2

        self.app = QApplication([])
        self.size = (width, height)
        self.qpicamera2 = QPicamera2(picam2, width=width, height=height)
        self.qpicamera2.setWindowTitle("QtPreview")
        self.qpicamera2.show()
        picam2.asynchronous = True
        # Can't get Qt to exit tidily without this. Possibly an artifact of running
        # it in another thread?
        atexit.register(self.stop)
        self.event.set()

        self.app.exec()

        atexit.unregister(self.stop)
        self.qpicamera2.picamera2.asynchronous = False
        # Again, all necessary to keep Qt quiet.
        del self.qpicamera2.label
        del self.qpicamera2.camera_notifier
        del self.qpicamera2
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
