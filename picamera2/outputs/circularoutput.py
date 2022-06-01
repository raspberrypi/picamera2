import collections
from multiprocessing import Lock

from .fileoutput import FileOutput


class CircularOutput(FileOutput):
    def __init__(self, file=None, buffersize=30 * 5):
        """Creates circular buffer for 5s worth of 30fps frames"""
        super().__init__(file)
        self._lock = Lock()
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
        with self._lock:
            self._buffersize = value
            self._circular = collections.deque(maxlen=value)

    def outputframe(self, frame, keyframe=True):
        """Write frame to circular buffer"""
        with self._lock:
            if self._buffersize == 0:
                return
            self._circular += [(frame, keyframe)]
        """Output frame to file"""
        if self._fileoutput is not None and self.recording:
            if self._firstframe:
                keyframe = False
                with self._lock:
                    for _ in range(len(self._circular)):
                        frame, keyframe = self._circular.popleft()
                        if keyframe:
                            break
                if keyframe:
                    self._write(frame)
                    self._firstframe = False
            else:
                with self._lock:
                    frame, keyframe = self._circular.popleft()
                self._write(frame)

    def stop(self):
        """Close file handle and prevent recording"""
        self.recording = False
        with self._lock:
            while self._circular:
                frame, keyframe = self._circular.popleft()
                self._write(frame)
        self.close()
