from .output import Output


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

    def outputframe(self, frame, keyframe=True):
        """Output frame to file"""
        if self._fileoutput is not None and self.recording:
            if self._firstframe:
                if not keyframe:
                    return
                else:
                    self._firstframe = False
            self._fileoutput.write(frame)
            self._fileoutput.flush()

    def stop(self):
        """Close file handle and prevent recording"""
        super().stop()
        self._fileoutput.close()
