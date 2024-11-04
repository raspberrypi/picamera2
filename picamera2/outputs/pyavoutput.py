import av

from .output import Output


class PyavOutput(Output):
    """
    The PyavOutput class outputs an encoded video, and optionally audio, stream using PyAV.

    PyAv is a Python interface to libav, used by FFmpeg, and therefore can accept many different output
    types and destinations, in the same way as FFmpeg.

    The PyavOutput calls directly into libav through its Python layer, and does not pipe encoded frames
    out to a separate process like the FfmpegOutput. The PyavOutput integration means we can pass precise
    timestamps, and are not subject to the hazards of FFmpeg re-timestamping everything as it gets piped
    back in.
    """

    def __init__(self, output_name, format=None, pts=None):
        super().__init__(pts=pts)
        self._output_name = output_name
        self._format = format
        self._streams = {}
        self._container = None
        # A user can set this to get notifications of failures.
        self.error_callback = None

    def _add_stream(self, encoder_stream, codec_name, **kwargs):
        # The output container that does the muxing needs to know about the streams for which packets
        # will be sent to it. It literally needs to copy them for the output container.
        stream = self._container.add_stream(codec_name, **kwargs)

        if codec_name == "mjpeg":
            # Well, this is nasty. MJPEG seems to need this.
            stream.codec_context.color_range = 2  # JPEG (full range)

        self._streams[encoder_stream] = stream

    def start(self):
        """Start the PyavOutput."""
        self._container = av.open(self._output_name, "w", format=self._format)
        super().start()

    def stop(self):
        """Stop the PyavOutput."""
        super().stop()
        if self._container:
            try:
                self._container.close()
            except Exception:
                pass
            self._container = None

    def outputframe(self, frame, keyframe=True, timestamp=None, packet=None, audio=False):
        """Output an encoded frame using PyAv."""
        if self.recording and self._container:
            orig_stream = packet.stream
            if orig_stream not in self._streams:
                raise RuntimeError("Stream not found in PyavOutput")
            # Here we replace in encoder's stream by the corresponding one for our output container.
            packet.stream = self._streams[orig_stream]

            try:
                self._container.mux(packet)
            except Exception as e:
                try:
                    self._container.close()
                except Exception:
                    pass
                self._container = None
                if self.error_callback:
                    self.error_callback(e)

            # Put the original stream back, just in case the encoder has multiple outputs and will pass
            # it to each one.
            packet.stream = orig_stream
            self.outputtimestamp(timestamp)
