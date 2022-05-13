from v4l2 import *
from ..outputs import Output

class Encoder:

    def __init__(self):
        self._width = 0
        self._height = 0
        self._stride = 0
        self._format = None
        self._output = None
        self._running = False

    @property
    def width(self):
        return self._width

    @width.setter
    def width(self, value):
        if not isinstance(value, int):
            raise RuntimeError("Width must be integer")
        self._width = value

    @property
    def height(self):
        return self._height

    @height.setter
    def height(self, value):
        if not isinstance(value, int):
            raise RuntimeError("Height must be integer")
        self._height = value

    @property
    def stride(self):
        return self._stride

    @stride.setter
    def stride(self, value):
        if not isinstance(value, int):
            raise RuntimeError("Stride must be integer")
        self._stride = value

    @property
    def format(self):
        return self._format

    @format.setter
    def format(self, value):
        if value == "RGB888":
            self._format = V4L2_PIX_FMT_BGR24
        elif value == "YUV420":
            self._format = V4L2_PIX_FMT_YUV420
        elif value == "XBGR8888":
            self._format = V4L2_PIX_FMT_BGR32
        elif value == "XRGB8888":
            self._format = V4L2_PIX_FMT_RGBA32
        else:
            raise RuntimeError("Invalid format")

    @property
    def output(self):
        return self._output

    @output.setter
    def output(self, value):
        if not isinstance(value, Output):
            raise RuntimeError("Must pass Output")
        self._output = value

    def encode(self, stream, request):
        pass

    def _start(self):
        if self._running:
            raise RuntimeError("Encoder already running")
        self._running = True
        if self.output:
            self.output.start()

    def _stop(self):
        self._running = False
        self.output.stop()
