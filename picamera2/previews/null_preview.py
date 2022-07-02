import picamera2.picamera2
import threading


class NullPreview:
    def thread_func(self, picam2):
        import selectors

        sel = selectors.DefaultSelector()
        sel.register(picam2.camera_manager.efd, selectors.EVENT_READ, self.handle_request)
        self.event.set()

        while self.running:
            events = sel.select(0.2)
            for key, mask in events:
                callback = key.data
                callback(picam2)


    def __init__(self, x=None, y=None, width=None, height=None):
        # Ignore width and height as they are meaningless. We only accept them so as to
        # be a drop-in replacement for the Qt/DRM previews.
        self.size = (width, height)
        self.event = threading.Event()
        self.picam2 = None

    def start(self, picam2):
        self.picam2 = picam2
        self.thread = threading.Thread(target=self.thread_func, args=(picam2,))
        self.thread.setDaemon(True)
        self.running = True
        self.thread.start()
        self.event.wait()

    def set_overlay(self, overlay):
        # This only exists so as to have the same interface as other preview windows.
        pass

    def handle_request(self, picam2):
        completed_request = picam2.process_requests()
        if completed_request:
            completed_request.release()

    def stop(self):
        self.running = False
        self.thread.join()
        self.picam2 = None
