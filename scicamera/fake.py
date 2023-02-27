from threading import Event, Thread
from typing import Any, Dict

import numpy as np

from scicamera.actions import RequestMachinery
from scicamera.request import CompletedRequest


def make_fake_image(shape, dtype=np.uint8):
    img = np.zeros(shape + (3,), dtype=dtype)
    w, h = shape
    img[0 : w / 3, :, 0] = 255
    img[w / 3 : 2 * w / 3, :, 1] = 255
    img[2 * w / 3 :, :, 2] = 255
    return img


class FakeCompletedRequest(CompletedRequest):
    def __init__(self, fake_size: tuple):
        self._fake_size = fake_size

    def acquire(self):
        pass

    def release(self):
        pass

    def get_config(self, name: str) -> Dict[str, Any]:
        """Fetch the configuration for the named stream."""
        return {}

    def get_buffer(self, name: str) -> np.ndarray:
        """Make a 1d numpy array from the named stream's buffer."""
        return make_fake_image(self._fake_size).flatten()

    def get_metadata(self) -> Dict[str, Any]:
        """Fetch the metadata corresponding to this completed request."""
        return {}


class FakeCamera(RequestMachinery):
    def __init__(self) -> None:
        super().__init__()
        self._t = Thread(target=lambda x: None, daemon=True)
        self._t.start()
        self._t.join()
        self._abort = Event()

    def _run(self):
        while not self._abort.wait(0.1):
            request = FakeCompletedRequest((640, 480))
            self.add_completed_request(request)

    def start(self) -> None:
        self._t = Thread(target=self._run)
        self._abort.clear()
        self._t.start()

    def stop(self) -> None:
        self._abort.set()
        self._t.join()

    def close(self) -> None:
        if self._t.is_alive():
            self.stop()
