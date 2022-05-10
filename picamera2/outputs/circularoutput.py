import collections
from .fileoutput import FileOutput


class CircularOutput(FileOutput):
    def __init__(self, file=None, buffersize=30 * 5):
        """Creates circular buffer for 5s worth of 30fps frames"""
        super().__init__(file)
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

    def outputframe(self, frame, keyframe=True):
        """Write frame to circular buffer"""
        if self._circular is not None:
            self._circular += [(frame, keyframe)]
        else:
            return
        """Output frame to file"""
        if self._fileoutput is not None and self.recording:
            if self._firstframe:
                keyframe = False
                for _ in range(len(self._circular)):
                    frame, keyframe = self._circular.popleft()
                    if keyframe:
                        break
                if keyframe:
                    self._fileoutput.write(frame)
                    self._fileoutput.flush()
                    self._firstframe = False
            else:
                frame, keyframe = self._circular.popleft()
                self._fileoutput.write(frame)
                self._fileoutput.flush()

    def stop(self):
        """Close file handle and prevent recording"""
        self.recording = False
        if self._circular is not None:
            for frame, keyframe in self._circular:
                self._fileoutput.write(frame)
                self._fileoutput.flush()
        self._fileoutput.close()
