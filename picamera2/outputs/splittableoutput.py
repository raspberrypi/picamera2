from threading import Event

from .output import Output


class SplittableOutput(Output):
    """
    The SplittableOutput passes the encoded bitstream to another output (or drops them if there isn't one).

    It can be told to "split" the current output that it's been writing to, to another one. This means
    it switches seamlessly from the current output, which is closed, to a new one, without dropping
    any frames. By default, it performs the switch at a video keyframem though it can be told not to
    wait for one (by setting wait_for_keyframe to False).
    """

    def __init__(self, output=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._output = output
        self._new_output = None
        self._split_done = Event()
        self._streams = []

    def split_output(self, new_output, wait_for_keyframe=True):
        """
        Terminate the current output, switching seamlessly to the new one.

        If wait_for_keyframe is True, the switch only occurs when the next video keyframe is
        seen. Otherwise the switch happens immediately.

        THe function returns only when the switch has happened, which may entail waiting for a
        video keyframe, and the old output has been closed.
        """
        old_output = self._output
        # Start the new outoput in this thread, then schedule outputframe to make the switch.
        new_output.start()
        for encoder_stream, codec, kwargs in self._streams:
            new_output._add_stream(encoder_stream, codec, **kwargs)
        self._wait_for_keyframe = wait_for_keyframe
        self._new_output = new_output
        # Wait for the switch-over to happen, and close the old output in this thread too.
        self._split_done.wait()
        self._split_done.clear()
        if old_output:
            old_output.stop()

    def outputframe(self, frame, keyframe=True, timestamp=None, packet=None, audio=False):
        # Audio frames probably always say they're keyframes, but we must wait for a video one.
        if self._new_output and (not self._wait_for_keyframe or (not audio and keyframe)):
            self._split_done.set()
            # split_output will close the old output.
            self._output = self._new_output
            self._new_output = None
        if self._output:
            self._output.outputframe(frame, keyframe, timestamp, packet, audio)

    def start(self):
        super().start()
        if self._output:
            self._output.start()

    def stop(self):
        super().stop()
        if self._output:
            self._output.stop()

    def _add_stream(self, encoder_stream, codec_name, **kwargs):
        # The underlying output may need to know what streams it's dealing with, so we must
        # remember them.
        self._streams.append((encoder_stream, codec_name, kwargs))
        # Forward immediately to the output if we were given one initially.
        if self._output:
            self._output._add_stream(encoder_stream, codec_name, **kwargs)
