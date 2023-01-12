"""Circular buffer"""

import collections
import io
from multiprocessing import Lock
from typing import Optional, Union

from .fileoutput import FileOutput


class CircularOutput(FileOutput):
    """Circular buffer implementation for file output"""

    def __init__(self,
                 file: Union[None, str, io.BufferedIOBase] = None,
                 pts: Union[None, str, io.BufferedWriter] = None,
                 buffersize: int = 30 * 5,
                 outputtofile: bool = True) -> None:
        """Creates circular buffer for 5s worth of 30fps frames

        :param file: File to write frames to, defaults to None
        :type file: str or BufferedIOBase, optional
        :param pts: File to write timestamps to, defaults to None
        :type pts: str or BufferedWriter, optional
        :param buffersize: Number of frames, defaults to 30*5
        :type buffersize: int, optional
        :param outputtofile: Boolean, whether to always write frames to file
        :type outputtofile: bool
        """
        super().__init__(file, pts=pts)
        self._lock = Lock()
        self.buffersize = buffersize
        self.outputtofile = outputtofile

    @property
    def buffersize(self) -> int:
        """Returns size of buffer"""
        return self._buffersize

    @buffersize.setter
    def buffersize(self, value: int) -> None:
        """Create buffer for specified number of frames"""
        if not isinstance(value, int):
            raise RuntimeError("Buffer size must be integer")
        with self._lock:
            self._buffersize = value
            self._circular = collections.deque(maxlen=value)

    def outputframe(self, frame: bytes, keyframe: bool = True, timestamp: Optional[int] = None) -> None:
        """Write frame to circular buffer

        :param frame: Frame
        :type frame: bytes
        :param keyframe: Whether frame is a keyframe, defaults to True
        :type keyframe: bool, optional
        :param timestamp: Timestamp of frame
        :type timestamp: int
        """
        with self._lock:
            if self._buffersize == 0:
                return
            self._circular += [(frame, keyframe)]
        """Output frame to file"""
        if self._fileoutput is not None and self.recording and self.outputtofile:
            if self._firstframe:
                keyframe = False
                with self._lock:
                    for _ in range(len(self._circular)):
                        frame, keyframe = self._circular.popleft()
                        if keyframe:
                            break
                if keyframe:
                    self._write(frame, timestamp)
                    self._firstframe = False
            else:
                with self._lock:
                    frame, keyframe = self._circular.popleft()
                self._write(frame, timestamp)

    def stop(self) -> None:
        """Close file handle and prevent recording"""
        self.recording = False
        key = False
        with self._lock:
            while self._circular:
                frame, keyframe = self._circular.popleft()
                if not self.outputtofile:
                    if not key:
                        if keyframe:
                            self._write(frame)
                            key = True
                    else:
                        self._write(frame)
                else:
                    self._write(frame)
        self.close()
