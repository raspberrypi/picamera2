from __future__ import annotations

import mmap
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field
from functools import partial
from logging import getLogger
from typing import Any, Callable

import libcamera
import numpy as np

import picamera2.formats as formats
from picamera2.helpers import Helpers
from picamera2.lc_helpers import lc_unpack

_log = getLogger(__name__)


class _MappedBuffer:
    def __init__(self, request, stream):
        stream = request.camera.stream_map[stream]
        self.__fb = request.request.buffers[stream]

    def __enter__(self):
        # Check if the buffer is contiguous and find the total length.
        fd = self.__fb.planes[0].fd
        planes_metadata = self.__fb.metadata.planes
        buflen = 0
        for p, p_metadata in zip(self.__fb.planes, planes_metadata):
            # bytes_used is the same as p.length for regular frames, but correctly reflects
            # the compressed image size for MJPEG cameras.
            buflen = buflen + p_metadata.bytes_used
            if fd != p.fd:
                raise RuntimeError("_MappedBuffer: Cannot map non-contiguous buffer!")

        self.__mm = mmap.mmap(
            fd, buflen, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE
        )
        return self.__mm

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.__mm is not None:
            self.__mm.close()


# TODO (meawoppl) - Flatten into the above class using an np array view.
# or at the very least actully use the context manager protocol it reps.
class MappedArray:
    def __init__(self, request, stream, reshape=True):
        self.__request = request
        self.__stream = stream
        self.__buffer = _MappedBuffer(request, stream)
        self.__array = None
        self.__reshape = reshape

    def __enter__(self):
        b = self.__buffer.__enter__()
        array = np.array(b, copy=False, dtype=np.uint8)

        if self.__reshape:
            config = self.__request.camera.camera_config[self.__stream]
            fmt = config["format"]
            w, h = config["size"]
            stride = config["stride"]

            # Turning the 1d array into a 2d image-like array only works if the
            # image stride (which is in bytes) is a whole number of pixels. Even
            # then, if they don't match exactly you will get "padding" down the RHS.
            # Working around this requires another expensive copy of all the data.
            if fmt in ("BGR888", "RGB888"):
                if stride != w * 3:
                    array = array.reshape((h, stride))
                    array = array[:, : w * 3]
                array = array.reshape((h, w, 3))
            elif fmt in ("XBGR8888", "XRGB8888"):
                if stride != w * 4:
                    array = array.reshape((h, stride))
                    array = array[:, : w * 4]
                array = array.reshape((h, w, 4))
            elif fmt in ("YUV420", "YVU420"):
                # Returning YUV420 as an image of 50% greater height (the extra bit continaing
                # the U/V data) is useful because OpenCV can convert it to RGB for us quite
                # efficiently. We leave any packing in there, however, as it would be easier
                # to remove that after conversion to RGB (if that's what the caller does).
                array = array.reshape((h * 3 // 2, stride))
            elif formats.is_raw(fmt):
                array = array.reshape((h, stride))
            else:
                raise RuntimeError("Format " + fmt + " not supported")

        self.__array = array
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.__array is not None:
            del self.__array
        self.__buffer.__exit__(exc_type, exc_value, exc_traceback)

    @property
    def array(self):
        return self.__array


# TODO(meawoppl) - Make Completed Requests only exist inside of a context manager
# This remove all the bizzare locking and reference counting we are doing here manually
class CompletedRequest:
    def __init__(self, request, camera):
        self.request = request
        self.ref_count = 1
        self.lock = threading.Lock()
        self.camera = camera
        self.stop_count = camera.stop_count
        self.config = self.camera.camera_config.copy()

    def acquire(self):
        """Acquire a reference to this completed request, which stops it being recycled back to
        the camera system.
        """
        with self.lock:
            if self.ref_count == 0:
                raise RuntimeError("CompletedRequest: acquiring lock with ref_count 0")
            self.ref_count += 1

    def release(self):
        """Release this completed frame back to the camera system (once its reference count
        reaches zero).
        """
        with self.lock:
            self.ref_count -= 1
            if self.ref_count < 0:
                raise RuntimeError("CompletedRequest: lock now has negative ref_count")

            if self.ref_count > 0:
                return

            # If the camera has been stopped since this request was returned then we
            # can't recycle it.
            if self.camera.camera and self.stop_count == self.camera.stop_count:
                self.camera.recycle_request(self.request)
            else:
                _log.warning(
                    "Camera stopped before request could be recycled (Discarding it)"
                )
            self.request = None

    def make_buffer(self, name: str):
        """Make a 1d numpy array from the named stream's buffer."""
        if self.camera.stream_map.get(name, None) is None:
            raise RuntimeError(f'Stream "{name}" is not defined')
        with _MappedBuffer(self, name) as b:
            return np.array(b, dtype=np.uint8)

    def get_metadata(self):
        """Fetch the metadata corresponding to this completed request."""
        return lc_unpack(self.request.metadata)

    def make_array(self, name: str):
        """Make a 2d numpy array from the named stream's buffer."""
        return Helpers.make_array(self.make_buffer(name), self.config[name])

    def make_image(self, name: str, width=None, height=None):
        """Make a PIL image from the named stream's buffer."""
        return Helpers.make_image(
            self.make_buffer(name), self.config[name], width, height
        )

    def save(self, name, file_output, format=None):
        """Save a JPEG or PNG image of the named stream's buffer."""
        return Helpers.save(
            self.camera, self.make_image(name), self.get_metadata(), file_output, format
        )


@dataclass
class LoopTask:
    call: Callable[[CompletedRequest], Any] | callable[[], Any]

    needs_request: bool = True

    future: Future = field(init=False, default_factory=Future)

    @classmethod
    def with_request(cls, call, *args):
        return cls(call=partial(call, *args), needs_request=True)

    @classmethod
    def without_request(cls, call, *args):
        return cls(call=partial(call, *args), needs_request=False)

    def __post_init__(self):
        self.future.set_running_or_notify_cancel()
