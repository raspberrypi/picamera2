"""Output frames from encoder"""

import io
from typing import Optional, Union


class Output:
    """Handles output functionality of encoders"""

    def __init__(self, pts: Union[None, str, io.BufferedWriter] = None) -> None:
        """Start output, with recording set to False

        :param pts: File to write timestamps to, defaults to None
        :type pts: str or BufferedWriter, optional
        """
        self.recording = False
        self.ptsoutput = pts

    def start(self) -> None:
        """Start recording"""
        self.recording = True

    def stop(self) -> None:
        """Stop recording"""
        self.recording = False

    def outputframe(self, frame: bytes, keyframe: bool = True, timestamp: Optional[int] = None) -> None:
        """Outputs frame from encoder

        :param frame: Frame
        :type frame: bytes
        :param keyframe: Whether frame is a keyframe, defaults to True
        :type keyframe: bool, optional
        :param timestamp: Timestamp of frame
        :type timestamp: int
        """

    def outputtimestamp(self, timestamp: Optional[int]) -> None:
        """Output timestamp to file

        :param timestamp: Timestamp to write to file
        :type timestamp: int
        """
        if self.ptsoutput is not None and timestamp is not None:
            print(f"{timestamp // 1000}.{timestamp % 1000:03}", file=self.ptsoutput, flush=True)

    @property
    def ptsoutput(self) -> Optional[io.BufferedWriter]:
        """Return file handle"""
        return self._ptsoutput

    @ptsoutput.setter
    def ptsoutput(self, file: Union[None, str, io.BufferedWriter]):
        """Change file to output pts file to"""
        if file is None:
            self._ptsoutput = None
        else:
            if isinstance(file, str):
                self._ptsoutput = open(file, "w")
            else:
                self._ptsoutput = file
