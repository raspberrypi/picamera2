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
        # manipulate _output, which controls whether outputframe will do anything.
        # THe application API does not have it's own lock, because there doesn't seem to be a
        # need to drive it from different threads (though we could add one if necessary).
        self._lock = Lock()
        if buffer_duration_ms < 0:
            raise RuntimeError("buffer_duration_ms may not be negative")
        self._buffer_duration_ms = buffer_duration_ms
        self._circular = collections.deque()
        self._output = None
        self._streams = []
        self._first_frame = True
        self._time_offset = 0

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

        output.start()
        # Some outputs (PyavOutput) may need to know about the encoder's streams.
        for encoder_stream, codec, kwargs in self._streams:
            output._add_stream(encoder_stream, codec, **kwargs)

        # Now it's OK for the background thread to output frames.
        with self._lock:
            self._output = output
            self._first_frame = True

    def close_output(self):
        """Close an output object."""
        if not self._output:
            raise RuntimeError("No underlying output has been opened")

        # After this, we guarantee that the background thread will never use the output.
        output = self._output
        with self._lock:
            self._output = None

        output.stop()

    def _flush(self, timestamp_now, output):
        # Flush out anything that is time-expired compared to timestamp_now.
        # If timestamp_now is None, flush everything.
        while self._circular and (front := self._circular[0]):
            frame, keyframe, timestamp, packet, audio = front

            if timestamp_now and timestamp_now - timestamp < self.buffer_duration_ms * 1000:
                break

            # We need to drop this entry, writing it out if we can.
            self._circular.popleft()

            if keyframe and not audio:
                if self._first_frame:
                    self._time_offset = timestamp
                self._first_frame = False

            if not self._first_frame and output:
                new_timestamp = timestamp - self._time_offset
                if new_timestamp >= 0:
                    output.outputframe(frame, keyframe, new_timestamp, packet, audio)

    def outputframe(self, frame, keyframe=True, timestamp=None, packet=None, audio=False):
        """Write frame to circular buffer"""
        with self._lock:
            if self._buffer_duration_ms == 0 or not self.recording:
                return

            # Add this new frame to the buffer and flush anything that is now expired.
            self._circular.append((frame, keyframe, timestamp, packet, audio))
            self._flush(timestamp, self._output)

    def start(self):
        """Start recording in the circular buffer."""
        with self._lock:
            if self.recording:
                raise RuntimeError("Circular output is running")
            self.recording = True

    def stop(self):
        """Close file handle and stop recording"""
        output = self._output
        with self._lock:
            if not self.recording:
                raise RuntimeError("Circular output was not started")
            self.recording = False
            self._output = None

        # At this point the background thread can't be using the circular buffer or the output,
        # so we can flush everything out.
        if output:
            self._flush(None, output)
            output.stop()

    def _add_stream(self, encoder_stream, codec_name, **kwargs):
        # Notice the PyavOutput of a stream that will be sending it packets to write out. It will need
        # to forward these whenever a new underlying output is opened.
        self._streams.append((encoder_stream, codec_name, kwargs))
