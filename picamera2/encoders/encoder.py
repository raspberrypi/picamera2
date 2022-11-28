"""Encoder functionality"""

import threading
from enum import Enum
from typing import Optional

from v4l2 import V4L2_PIX_FMT_BGR24, V4L2_PIX_FMT_YUV420, V4L2_PIX_FMT_BGR32, V4L2_PIX_FMT_RGBA32

from ..outputs import Output
from ..request import _MappedBuffer, CompletedRequest


class Quality(Enum):
    """Enum type to describe the quality wanted from an encoder. This may be passed
    if a specific value (such as bitrate) has not been set."""
    VERY_LOW = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    VERY_HIGH = 4


class Encoder:
    """Base class for encoders"""

    _format : Optional[int]

    def __init__(self):
        """Initialises encoder"""
        self._width = 0
        self._height = 0
        self._stride = 0
        self._format = None
        self._output = []
        self._running = False
        self._lock = threading.Lock()
        self.firsttimestamp = None

    @property
    def width(self) -> int:
        """Gets width

        :return: Width of frames
        :rtype: int
        """
        return self._width

    @width.setter
    def width(self, value) -> None:
        """Sets width

        :param value: Width
        :type value: int
        :raises RuntimeError: Failed to set width
        """
        if not isinstance(value, int):
            raise RuntimeError("Width must be integer")
        self._width = value

    @property
    def height(self) -> int:
        """Gets height

        :return: Height of frames
        :rtype: int
        """
        return self._height

    @height.setter
    def height(self, value) -> None:
        """Sets height

        :param value: Height
        :type value: int
        :raises RuntimeError: Failed to set height
        """
        if not isinstance(value, int):
            raise RuntimeError("Height must be integer")
        self._height = value

    @property
    def stride(self) -> int:
        """Gets stride

        :return: Stride
        :rtype: int
        """
        return self._stride

    @stride.setter
    def stride(self, value) -> None:
        """Sets stride

        :param value: Stride
        :type value: int
        :raises RuntimeError: Failed to set stride
        """
        if not isinstance(value, int):
            raise RuntimeError("Stride must be integer")
        self._stride = value

    @property
    def format(self) -> Optional[int]:
        """Get current format

        :return: Current format
        :rtype: int
        """
        return self._format

    @format.setter
    def format(self, value: str) -> None:
        """Sets input format to encoder

        :param value: Format
        :type value: str
        :raises RuntimeError: Invalid format
        """
        if value == "RGB888":
            self._format = V4L2_PIX_FMT_BGR24
        elif value == "YUV420":
            self._format = V4L2_PIX_FMT_YUV420
        elif value == "XBGR8888":
            self._format = V4L2_PIX_FMT_BGR32
        elif value == "XRGB8888":
            self._format = V4L2_PIX_FMT_RGBA32
        else:
            if type(self) is Encoder:
                """Currently allow any format that is
                passed, when Encoder used directly.
                We can't use Picamera2.is_raw(value) etc.
                to validate formats here, as we get a circular import
                when trying to import Picamera2
                """
                self._format = value
            else:
                raise RuntimeError("Invalid format")

    @property
    def output(self):
        """Gets output objects

        :return: Output object list or single Output object
        :rtype: List[Output]
        """
        if len(self._output) == 1:
            return self._output[0]
        else:
            return self._output

    @output.setter
    def output(self, value):
        """Sets output object, to write frames to

        :param value: Output object
        :type value: Output
        :raises RuntimeError: Invalid output passed
        """
        if isinstance(value, list):
            for out in value:
                if not isinstance(out, Output):
                    raise RuntimeError("Must pass Output")
        elif isinstance(value, Output):
            value = [value]
        else:
            raise RuntimeError("Must pass Output")
        self._output = value

    def encode(self, stream, request: CompletedRequest) -> None:
        """Encode a frame

        :param stream: Stream
        :type stream: stream
        :param request: Request
        :type request: request
        """
        with self._lock:
            self._encode(stream, request)

    def _encode(self, stream, request: CompletedRequest) -> None:
        fb = request.request.buffers[stream]
        timestamp_us = self._timestamp(fb)
        with _MappedBuffer(request, request.picam2.encode_stream_name) as b:
            self.outputframe(b, keyframe=True, timestamp=timestamp_us)

    def start(self) -> None:
        with self._lock:
            if self._running:
                raise RuntimeError("Encoder already running")
            self._running = True
            for out in self._output:
                out.start()
            self._start()

    def _start(self) -> None:
        pass

    def stop(self):
        with self._lock:
            self._running = False
            for out in self._output:
                out.stop()
            self._stop()

    def _stop(self) -> None:
        pass

    def outputframe(self, frame, keyframe=True, timestamp=None) -> None:
        """Writes a frame

        :param frame: Frame
        :type frame: bytes
        :param keyframe: Whether frame is a keyframe or not, defaults to True
        :type keyframe: bool, optional
        """
        for out in self._output:
            out.outputframe(frame, keyframe, timestamp)

    def _setup(self, quality: Quality) -> None:
        pass

    def _timestamp(self, fb) -> int:
        ts = int(fb.metadata.timestamp / 1000)
        if self.firsttimestamp is None:
            self.firsttimestamp = ts
            timestamp_us = 0
        else:
            timestamp_us = ts - self.firsttimestamp
        return timestamp_us
