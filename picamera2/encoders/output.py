import collections


class Output:
    def __init__(self):
        self.recording = False

    def start(self):
        self.recording = True

    def stop(self):
        self.recording = False

    def outputframe(self, frame):
        pass


class FileOutput(Output):
    def __init__(self, file=None):
        super().__init__()
        self.fileoutput = file

    @property
    def fileoutput(self):
        return self._fileoutput

    @fileoutput.setter
    def fileoutput(self, file):
        if file is None:
            self._fileoutput = None
        else:
            if isinstance(file, str):
                self._fileoutput = open(file, "wb")
            else:
                self._fileoutput = file

    def outputframe(self, frame):
        if self._fileoutput is not None and self.recording:
            self._fileoutput.write(frame)
            self._fileoutput.flush()

    def stop(self):
        super().stop()
        self._fileoutput.close()


class CircularOutput(Output):
    def __init__(self, filename=None, buffersize=30 * 5):
        super().__init__()
        if filename is None:
            self._circularoutput = None
        else:
            self._circularoutput = open(filename, "wb")
        self.buffersize = buffersize

    @property
    def buffersize(self):
        return self._buffersize

    @buffersize.setter
    def buffersize(self, value):
        if not isinstance(value, int):
            raise RuntimeError("Buffer size must be integer")
        self._buffersize = value
        if value == 0:
            self._circular = None
        else:
            self._circular = collections.deque(maxlen=value)

    def dumpbuffer(self, filename=None):
        if filename is None:
            if self._filename is None:
                raise RuntimeError("Need to set filename")
            filename = self._filename
        output = open(filename, "wb")
        first = False
        lastiframe = None
        index = 0
        circ = list(self._circular)
        for frame in circ:
            naltype = frame[4] & 0x1F
            if naltype == 0x7 or naltype == 0x8:
                first = True
                lastiframe = index
            if first:
                output.write(frame)
            index += 1
        output.close()
        """
        output2 = open(filename2, "wb")
        if lastiframe is not None:
            for frame in circ[lastiframe:len(circ)]:
                output2.write(frame)
        self._output = output2
        """

    def outputframe(self, frame):
        if self._circular is not None:
            self._circular += [frame]


class CircularFileOutput(FileOutput, CircularOutput):
    def __init__(self):
        FileOutput.__init__(self)
        CircularOutput.__init__(self)

    def outputframe(self, frame):
        FileOutput.outputframe(self, frame)
        CircularOutput.outputframe(self, frame)
