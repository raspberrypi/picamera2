import io

class Encoder:
    
    def __init__(self):
        self._width = 0
        self._height = 0
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
    def output(self):
        return self._output

    @output.setter
    def output(self, value):
        if not isinstance(value, io.BufferedIOBase):
            raise RuntimeError("Must pass BufferedIOBase")
        self._output = value

    def encode(self, stream, request):
        pass

    def _start(self):
        if self._running:
            raise RuntimeError("Encoder already running")
        self._running = True

    def _stop(self):
        self._running = False
