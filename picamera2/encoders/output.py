import collections


class Output:
    def __init__(self):
        self.recording = False

    def start(self):
        self.recording = True

    def stop(self):
        self.recording = False

    def outputframe(self, frame, keyframe=True):
        pass


class FileOutput(Output):
    def __init__(self, file=None):
        super().__init__()
        self.fileoutput = file
        self._firstframe = True
        self._before = None

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

    def before(self, file, file2):
        """Sets a 'before' file, which we write none-keyframes to
        which would normally be discarded"""
        self._before = open(file, "ab")
        self.fileoutput = file2

    def outputframe(self, frame, keyframe=True):
        """Output frame to file"""
        if self._fileoutput is not None and self.recording:
            if self._firstframe:
                if not keyframe:
                    if self._before is not None:
                        self._before.write(frame)
                        self._before.flush()
                    return
                else:
                    if self._before:
                        self._before.close()
                    self._before = None
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
        circ = list(self._circular)
        for frame, keyframe in circ:
            if keyframe:
                first = True
            if first:
                output.write(frame)
        output.close()

    def outputframe(self, frame, keyframe=True):
        """Write frame to circular buffer"""
        if self._circular is not None:
            self._circular += [(frame, keyframe)]


class CircularFileOutput(FileOutput, CircularOutput):
    def __init__(self):
        FileOutput.__init__(self)
        CircularOutput.__init__(self)

    def outputframe(self, frame, keyframe=True):
        """Write frame to both file and circular buffer"""
        FileOutput.outputframe(self, frame, keyframe)
        CircularOutput.outputframe(self, frame, keyframe)

    def dumpbuffer(self, filename, filename2=None):
        """Tag on none-keyframe frames to 'before' file if necessary"""
        if filename2 is None:
            CircularOutput.dumpbuffer(self, filename)
        else:
            CircularOutput.dumpbuffer(self, filename)
            FileOutput.before(self, filename, filename2)
