"""Write frames to a socket"""

import types

from .output import Output

MAX_DATAGRAM_SIZE = 65507


class SocketOutput(Output):
    """Socket handling functionality for encoders"""

    def __init__(self, socket=None, pts=None):
        """Initialise UDP output

        :param socket: Socket to write frames to, defaults to None
        :type socket: socket.socket, optional
        :param pts: File to write timestamps to, defaults to None
        :type pts: str or BufferedWriter, optional
        """
        super().__init__(pts=pts)
        self.dead = False
        self.socket = socket
        self._datagram = False
        self._firstframe = True
        self._before = None
        self._connectiondead = None

    @property
    def socket(self):
        """Return socket"""
        return self._socket

    @socket.setter
    def socket(self, socket):
        """Change socket to output frames to"""
        self._firstframe = True
        if socket is None:
            self._socket = None
        elif isinstance(socket, socket.socket):
            if self._socket is not None:
                self._socket.close()
            self._datagram = socket.type == socket.SOCK_DGRAM
            self._socket = socket

        else:
            raise RuntimeError("Must pass socket or None")

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

    def outputframe(self, frame, keyframe=True, timestamp=None):
        """Write frames to a UDP stream

        :param frame: Frame
        :type frame: bytes
        :param keyframe: Whether frame is a keyframe, defaults to True
        :type keyframe: bool, optional
        :param timestamp: Timestamp of frame
        :type timestamp: int
        """
        if self._socket is not None and self.recording:
            if self._firstframe:
                if not keyframe:
                    return
                else:
                    self._firstframe = False
            self._write(frame, timestamp)

    def stop(self):
        """Close socket and prevent recording"""
        super().stop()
        self.close()

    def close(self):
        """Close socket"""
        try:
            self._socket.close()
        except (ConnectionResetError, ConnectionRefusedError, BrokenPipeError) as e:
            self.dead = True
            if self._connectiondead is not None:
                self._connectiondead(e)

    def _write(self, frame, timestamp=None):
        try:
            if self._datagram:
                for i in range(0, len(frame), MAX_DATAGRAM_SIZE):
                    self._socket.send(frame[i:i + MAX_DATAGRAM_SIZE])
            else:
                self._socket.sendall(frame)
            self.outputtimestamp(timestamp)
        except (ConnectionResetError, ConnectionRefusedError, BrokenPipeError) as e:
            self.dead = True
            if self._connectiondead is not None:
                self._connectiondead(e)

