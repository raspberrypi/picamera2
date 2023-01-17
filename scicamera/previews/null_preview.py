"""Null preview"""
import selectors
import threading
from logging import getLogger

_log = getLogger(__name__)


class NullPreview:
    """Null Preview"""

    def thread_func(self, camera):
        """Thread function

        :param camera: Camera object
        :type camera: Camera
        """
        sel = selectors.DefaultSelector()
        sel.register(camera.notifyme_r, selectors.EVENT_READ, self.handle_request)
        self._started.set()

        # TODO(meawoppl) - abort flag and select can be polled in parallel
        # which will make startup/shutdown faster
        while not self._abort.is_set():
            events = sel.select(0.2)
            for key, _ in events:
                camera.notifymeread.read()
                callback = key.data
                callback(camera)

    def __init__(self, x=None, y=None, width=None, height=None, transform=None):
        """Initialise null preview

        :param x: X position, defaults to None
        :type x: int, optional
        :param y: Y position, defaults to None
        :type y: int, optional
        :param width: Width, defaults to None
        :type width: int, optional
        :param height: Height, defaults to None
        :type height: int, optional
        :param transform: Transform, defaults to None
        :type transform: libcamera.Transform, optional
        """
        # Ignore width and height as they are meaningless. We only accept them so as to
        # be a drop-in replacement for the Qt/DRM previews.
        self.size = (width, height)
        self._abort = threading.Event()
        self._started = threading.Event()
        self.camera = None

    def start(self, camera):
        """Starts null preview

        :param camera: Camera object
        :type camera: Camera
        """
        self.camera = camera
        self._started.clear()
        self._abort.clear()
        self.thread = threading.Thread(
            target=self.thread_func, daemon=True, args=(camera,)
        )
        self.thread.start()
        self._started.wait()

    def handle_request(self, camera):
        """Handle requests

        :param camera: Camera object
        :type camera: Camera
        """
        try:
            camera.process_requests()
        except Exception as e:
            _log.exception("Exception during process_requests()", exc_info=e)
            raise

    def stop(self):
        """Stop preview"""
        self._abort.set()
        self.thread.join()
        self.camera = None
