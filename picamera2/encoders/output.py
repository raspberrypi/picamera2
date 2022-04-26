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
        self._firstframe = True

    @property
    def fileoutput(self):
        """Return file handle"""
        return self._fileoutput

    @fileoutput.setter
    def fileoutput(self, file):
        """Change file to output frames to"""
        self._firstframe = True
        if file is None:
            self._fileoutput = None
        else:
            if isinstance(file, str):
                self._fileoutput = open(file, "wb")
            else:
                self._fileoutput = file

    def outputframe(self, frame):
        """Output frame to file"""
        if self._fileoutput is not None and self.recording:
            if self._firstframe:
                naltype = frame[4] & 0x1F
                if not (naltype == 0x7 or naltype == 0x8):
                    return  # Skip frame
                else:
                    self._firstframe = False
            self._fileoutput.write(frame)
            self._fileoutput.flush()

    def stop(self):
        """Close file handle and prevent recording"""
        super().stop()
        self._fileoutput.close()


class CircularOutput(Output):
    def __init__(self, filename=None, buffersize=30 * 5):
        """Creates circular buffer for 5s worth of 30fps frames"""
        super().__init__()
        if filename is None:
            self._circularoutput = None
        else:
            self._circularoutput = open(filename, "wb")
        self.buffersize = buffersize

    @property
    def buffersize(self):
        """Returns size of buffer"""
        return self._buffersize

    @buffersize.setter
    def buffersize(self, value):
        """Create buffer for specified number of frames"""
        if not isinstance(value, int):
            raise RuntimeError("Buffer size must be integer")
        self._buffersize = value
        if value == 0:
            self._circular = None
        else:
            self._circular = collections.deque(maxlen=value)

    def dumpbuffer(self, filename=None):
        """Dump buffer to specified file"""
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

    def outputframe(self, frame):
        """Write frame to circular buffer"""
        if self._circular is not None:
            self._circular += [frame]


class CircularFileOutput(FileOutput, CircularOutput):
    def __init__(self):
        FileOutput.__init__(self)
        CircularOutput.__init__(self)

    def outputframe(self, frame):
        """Write frame to both file and circular buffer"""
        FileOutput.outputframe(self, frame)
        CircularOutput.outputframe(self, frame)
