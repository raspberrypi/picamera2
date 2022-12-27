import time
from concurrent.futures import Future
from threading import Thread
from unittest.mock import Mock

from picamera2 import Picamera2
from picamera2.request import CompletedRequest


def mature_after_frames_or_timeout(
    camera: Picamera2, n_frames: int, timeout_seconds=5
) -> Future:
    """Return a future that will be mature after n_frames or 2 seconds."""
    future = Future()
    future.set_running_or_notify_cancel()
    mock = Mock()

    def timeout_thread():
        try:
            future.result(timeout=timeout_seconds)
        except TimeoutError as e:
            future.set_exception(e)
            camera.remove_request_callback(callback)

    Thread(target=timeout_thread, daemon=True).start()

    def callback(request: CompletedRequest):
        mock(request)
        if mock.call_count == n_frames:
            future.set_result(None)
            camera.remove_request_callback(callback)

    camera.add_request_callback(callback)

    return future
