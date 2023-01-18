"""Null preview"""
import threading
from logging import getLogger

_log = getLogger(__name__)


class NullPreview:
    """Null Preview"""

    def thread_func(self):
        """Thread function

        :param camera: Camera object
        :type camera: Camera
        """
        while not self._abort.is_set():
            if not self.camera.has_requests():
                self._abort.wait(0.01)
                continue

            try:
                self.camera.process_requests()
            except Exception as e:
                _log.exception("Exception during process_requests()", exc_info=e)
                raise

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
        self.camera = None

    def start(self, camera):
        """Starts null preview

        :param camera: Camera object
        :type camera: Camera
        """
        self.camera = camera
        self._abort.clear()
        self.thread = threading.Thread(target=self.thread_func, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop preview"""
        self._abort.set()
        self.thread.join()
        self.camera = None
