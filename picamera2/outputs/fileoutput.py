"""Writes frames to a file"""

import io
import socket
import types
from pathlib import Path

from .output import Output


class FileOutput(Output):
    """File handling functionality for encoders"""

    def __init__(self, file=None, pts=None, split=None):
        """Initialise file output

        :param file: File to write frames to, defaults to None
        :type file: str or BufferedIOBase or Path, optional
        :param pts: File to write timestamps to, defaults to None
        :type pts: str or BufferedWriter, optional
        :param split: Max transmission size of data, only applies to datagrams, defaults to None
        :type split: int, optional
        """
        super().__init__(pts=pts)
        self.dead = False
        self.fileoutput = file
        self._firstframe = True
        self._before = None
        self._connectiondead = None
        self._splitsize = split

    @property
    def fileoutput(self):
        """Return file handle"""
        return self._fileoutput

    @fileoutput.setter
    def fileoutput(self, file):
        """Change file to output frames to"""
        self._split = False
        self._firstframe = True
        self._needs_close = False
        if file is None:
            self._fileoutput = None
        else:
            if isinstance(file, str) or isinstance(file, Path):
                self._fileoutput = open(file, "wb")
                self._needs_close = True
            elif isinstance(file, io.BufferedIOBase):
                self._fileoutput = file
            else:
                raise RuntimeError("Must pass io.BufferedIOBase")
            if hasattr(self._fileoutput, "raw") and isinstance(self._fileoutput.raw, socket.SocketIO) and \
                    self._fileoutput.raw._sock.type == socket.SocketKind.SOCK_DGRAM:
                self._split = True

    @property
    def connectiondead(self):
        """Return callback"""
        return self._connectiondead

    @connectiondead.setter
    def connectiondead(self, _callback):
        """Callback for passing exceptions

        :param _callback: Callback that is called when exception caught
        :type _callback: function
        :raises RuntimeError: Must pass function
        """
        if isinstance(_callback, types.FunctionType) or _callback is None:
            self._connectiondead = _callback
        else:
            raise RuntimeError("Must pass callback function or None")

    def outputframe(self, frame, keyframe=True, timestamp=None, packet=None, audio=False):
        """Outputs frame from encoder

        :param frame: Frame
        :type frame: bytes
        :param keyframe: Whether frame is a keyframe, defaults to True
        :type keyframe: bool, optional
        :param timestamp: Timestamp of frame
        :type timestamp: int
        """
        if audio:
            raise RuntimeError("Fileoutput does not support audio")
        if self._fileoutput is not None and self.recording:
            if self._firstframe:
                if not keyframe:
                    return
                else:
                    self._firstframe = False
            self._write(frame, timestamp)

    def stop(self):
        """Close file handle and prevent recording"""
        super().stop()
        self.close()

    def close(self):
        """Closes all files"""
        try:
            if self._needs_close:
                self._fileoutput.close()
        except (ConnectionResetError, ConnectionRefusedError, BrokenPipeError) as e:
            self.dead = True
            if self._connectiondead is not None:
                self._connectiondead(e)

    def _write(self, frame, timestamp=None):
        try:
            if self._split:
                maxsize = 65507 if self._splitsize is None else self._splitsize
                tosend = len(frame)
                off = 0
                while tosend > 0:
                    lenv = min(tosend, maxsize)
                    self._fileoutput.write(frame[off:off + lenv])
                    self._fileoutput.flush()
                    off += lenv
                    tosend -= lenv
            else:
                self._fileoutput.write(frame)
                self._fileoutput.flush()
            self.outputtimestamp(timestamp)
        except (ConnectionResetError, ConnectionRefusedError, BrokenPipeError, ValueError) as e:
            self.dead = True
            if self._connectiondead is not None:
                self._connectiondead(e)
