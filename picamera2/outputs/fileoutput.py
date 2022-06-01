from .output import Output
import types


class FileOutput(Output):
    def __init__(self, file=None):
        super().__init__()
        self.dead = False
        self.fileoutput = file
        self._firstframe = True
        self._before = None
        self._connectiondead = None

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

    @property
    def connectiondead(self):
        """Return callback"""
        return self._connectiondead

    @connectiondead.setter
    def connectiondead(self, _callback):
        if isinstance(_callback, types.FunctionType) or _callback is None:
            self._connectiondead = _callback
        else:
            raise RuntimeError("Must pass callback function or None")

    def outputframe(self, frame, keyframe=True):
        """Output frame to file"""
        if self._fileoutput is not None and self.recording:
            if self._firstframe:
                if not keyframe:
                    return
                else:
                    self._firstframe = False
            self._write(frame)

    def stop(self):
        """Close file handle and prevent recording"""
        super().stop()
        self.close()

    def close(self):
        try:
            self._fileoutput.close()
        except (ConnectionResetError, ConnectionRefusedError, BrokenPipeError) as e:
            self.dead = True
            if self._connectiondead is not None:
                self._connectiondead(e)

    def _write(self, frame):
        try:
            self._fileoutput.write(frame)
            self._fileoutput.flush()
        except (ConnectionResetError, ConnectionRefusedError, BrokenPipeError) as e:
            self.dead = True
            if self._connectiondead is not None:
                self._connectiondead(e)
