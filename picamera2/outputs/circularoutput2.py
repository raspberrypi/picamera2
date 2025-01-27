"""Circular buffer"""

import collections
from threading import Lock

from .output import Output


class CircularOutput2(Output):
    """
    Circular buffer implementation, much like CircularOutput, but for general outputs.

    This means it can be used in conjunction with, for example, a PyavOutput to create time-shifted
    recordings of both video and audio straight to an mp4 file.

    Once the CircularOutput2 has been started, use the open_output method to start start recording
    a new output, and use close_output when finished. If the output has not been closed when the
    circular buffer is stopped, then the remainder of the buffer will be flush into the output.
    """

    def __init__(self, pts=None, buffer_duration_ms=5000):
        """Create a CircularOutput2."""
        super().__init__(pts=pts)
        # A note on locking. The lock is principally to protect outputframe, which is called by
        # the background encoder thread. Applications are going to call things like open_output,
        # close_output, start and stop. These only grab that lock for a short period of time to
        # manipulate _output_available, which controls whether outputframe will do anything.
        # THe application API does not have it's own lock, because there doesn't seem to be a
        # need to drive it from different threads (though we could add one if necessary).
        self._lock = Lock()
        if buffer_duration_ms < 0:
            raise RuntimeError("buffer_duration_ms may not be negative")
        self._buffer_duration_ms = buffer_duration_ms
        self._circular = collections.deque()
        self._output = None
        self._output_available = False
        self._streams = []

    @property
    def buffer_duration_ms(self):
        """Returns duration of the buffer in ms"""
        return self._buffer_duration_ms

    @buffer_duration_ms.setter
    def buffer_duration_ms(self, value):
        """Set buffer duration in ms, can even be changed dynamically"""
        with self._lock:
            self._buffer_duration_ms = value

    def open_output(self, output):
        """Open a new output object and start writing to it."""
        if self._output:
            raise RuntimeError("Underlying output must be closed first")

        self._output = output
        self._output.start()
        # Some outputs (PyavOutput) may need to know about the encoder's streams.
        for encoder_stream, codec, kwargs in self._streams:
            output._add_stream(encoder_stream, codec, **kwargs)

        # Now it's OK for the background thread to output frames.
        with self._lock:
            self._output_available = True
            self._first_frame = True

    def close_output(self):
        """Close an output object."""
        if not self._output:
            raise RuntimeError("No underlying output has been opened")

        # After this, we guarantee that the background thread will never use the output.
        with self._lock:
            self._output_available = False

        self._output.stop()
        self._output = None

    def _get_frame(self):
        # Fetch the next frame to be saved to the underlying output.
        if not self._circular:
            return
        if not self._first_frame:
            return self._circular.popleft()
        # Must skip ahead to the first I frame if we haven't seen one yet.
        while self._circular:
            entry = self._circular.popleft()
            _, key_frame, _, _, audio = entry
            # If there is audio, all audio frames are likely to be keyframes, so we must ignore them when
            # deciding when the streams can resume - only the video counts.
            if key_frame and not audio:
                self._first_frame = False
                return entry

    def outputframe(self, frame, keyframe=True, timestamp=None, packet=None, audio=False):
        """Write frame to circular buffer"""
        with self._lock:
            if self._buffer_duration_ms == 0 or not self.recording:
                return
            self._circular.append((frame, keyframe, timestamp, packet, audio))
            # Discard any expired buffer entries.
            while timestamp - self._circular[0][2] > self._buffer_duration_ms * 1000:
                self._circular.popleft()

            if self._output_available:
                # Actually write this to the underlying output.
                entry = self._get_frame()
                if entry:
                    self._output.outputframe(*entry)

    def start(self):
        """Start recording in the circular buffer."""
        with self._lock:
            if self.recording:
                raise RuntimeError("Circular output is running")
            self.recording = True

    def stop(self):
        """Close file handle and stop recording"""
        with self._lock:
            if not self.recording:
                raise RuntimeError("Circular output was not started")
            self._recording = False
            self._output_available = False

        # Flush out anything remaining in the buffer if the underlying output is still going
        # when we stop.
        if self._output:
            while (entry := self._get_frame()):
                self._output.outputframe(*entry)
            self._output.stop()
            self._output = None

    def _add_stream(self, encoder_stream, codec_name, **kwargs):
        # Notice the PyavOutput of a stream that will be sending it packets to write out. It will need
        # to forward these whenever a new underlying output is opened.
        self._streams.append((encoder_stream, codec_name, kwargs))
