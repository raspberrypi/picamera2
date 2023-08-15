"""Encoder functionality"""

import threading
from enum import Enum

from v4l2 import *

import picamera2.formats as formats

from ..outputs import Output
from ..request import _MappedBuffer


class Quality(Enum):
    """Enum type to describe the quality wanted from an encoder.

    This may be passed if a specific value (such as bitrate) has not been set.
    """

    VERY_LOW = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    VERY_HIGH = 4


class Encoder:
    """Base class for encoders"""

    def __init__(self):
        """Initialises encoder"""
        self._width = 0
        self._height = 0
        self._stride = 0
        self._format = None
        self._output = []
        self._running = False
        self._name = None
        self._lock = threading.Lock()
        self.firsttimestamp = None

    @property
    def running(self):
        return self._running

    @property
    def width(self):
        """Gets width

        :return: Width of frames
        :rtype: int
        """
        return self._width

    @width.setter
    def width(self, value):
        """Sets width

        :param value: Width
        :type value: int
        :raises RuntimeError: Failed to set width
        """
        if not isinstance(value, int):
            raise RuntimeError("Width must be integer")
        self._width = value

    @property
    def height(self):
        """Gets height

        :return: Height of frames
        :rtype: int
        """
        return self._height

    @height.setter
    def height(self, value):
        """Sets height

        :param value: Height
        :type value: int
        :raises RuntimeError: Failed to set height
        """
        if not isinstance(value, int):
            raise RuntimeError("Height must be integer")
        self._height = value

    @property
    def size(self):
        """Gets size

        :return: Size of frames as (width, height)
        :rtype: tuple
        """
        return (self._width, self._height)

    @size.setter
    def size(self, value):
        """Sets size

        :param value: Size
        :type value: tuple
        :raises RuntimeError: Failed to set size
        """
        if not isinstance(value, tuple) or len(value) != 2:
            raise RuntimeError("Size must be a tuple of two integers")
        self.width, self.height = value

    @property
    def stride(self):
        """Gets stride

        :return: Stride
        :rtype: int
        """
        return self._stride

    @stride.setter
    def stride(self, value):
        """Sets stride

        :param value: Stride
        :type value: int
        :raises RuntimeError: Failed to set stride
        """
        if not isinstance(value, int):
            raise RuntimeError("Stride must be integer")
        self._stride = value

    @property
    def format(self):
        """Get current format

        :return: Current format
        :rtype: int
        """
        return self._format

    @format.setter
    def format(self, value):
        """Sets input format to encoder

        :param value: Format
        :type value: str
        :raises RuntimeError: Invalid format
        """
        if value == "RGB888":
            self._format = V4L2_PIX_FMT_BGR24
        elif value == "BGR888":
            self._format = V4L2_PIX_FMT_RGB24
        elif value == "YUV420":
            self._format = V4L2_PIX_FMT_YUV420
        elif value == "XBGR8888":
            self._format = V4L2_PIX_FMT_BGR32
        elif value == "XRGB8888":
            self._format = V4L2_PIX_FMT_RGBA32
        else:
            formats.assert_format_valid(value)
            self._format = value

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

    @property
    def name(self):
        """Gets stream name

        :return: Name
        :rtype: str
        """
        return self._name

    @name.setter
    def name(self, value):
        """Sets stream name

        :param value: Name
        :type value: str
        :raises RuntimeError: Failed to set name
        """
        if not isinstance(value, str):
            raise RuntimeError("Name must be string")
        self._name = value

    def encode(self, stream, request):
        """Encode a frame

        :param stream: Stream
        :type stream: stream
        :param request: Request
        :type request: request
        """
        with self._lock:
            self._encode(stream, request)

    def _encode(self, stream, request):
        fb = request.request.buffers[stream]
        timestamp_us = self._timestamp(fb)
        with _MappedBuffer(request, self.name) as b:
            self.outputframe(b, keyframe=True, timestamp=timestamp_us)

    def start(self):
        with self._lock:
            if self._running:
                raise RuntimeError("Encoder already running")
            self._running = True
            for out in self._output:
                out.start()
            self._start()

    def _start(self):
        pass

    def stop(self):
        with self._lock:
            if not self._running:
                raise RuntimeError("Encoder already stopped")
            self._running = False
            for out in self._output:
                out.stop()
            self._stop()

    def _stop(self):
        pass

    def outputframe(self, frame, keyframe=True, timestamp=None):
        """Writes a frame

        :param frame: Frame
        :type frame: bytes
        :param keyframe: Whether frame is a keyframe or not, defaults to True
        :type keyframe: bool, optional
        """
        for out in self._output:
            out.outputframe(frame, keyframe, timestamp)

    def _setup(self, quality):
        pass

    def _timestamp(self, fb):
        ts = int(fb.metadata.timestamp / 1000)
        if self.firsttimestamp is None:
            self.firsttimestamp = ts
            timestamp_us = 0
        else:
            timestamp_us = ts - self.firsttimestamp
        return timestamp_us
