import av

from .output import Output


class PyavOutput(Output):
    """PyavOutput class"""

    def __init__(self, output_name, format=None, pts=None):
        super().__init__(pts=pts)
        self._output_name = output_name
        self._format = format
        self._streams = {}
        self._container = None
        # A user can set this to get notifications of failures.
        self.error_callback = None

    def _add_stream(self, encoder_stream, codec, **kwargs):
        stream = self._container.add_stream(codec, **kwargs)

        if codec == "mjpeg":
            # Well, this is nasty. MJPEG seems to need this.
            stream.codec_context.color_range = 2  # JPEG (full range)

        self._streams[encoder_stream] = stream

    def start(self):
        self._container = av.open(self._output_name, "w", format=self._format)
        super().start()

    def stop(self):
        super().stop()
        if self._container:
            try:
                self._container.close()
            except Exception:
                pass

    def outputframe(self, frame, keyframe=True, timestamp=None, packet=None):
        if self.recording and self._container:
            orig_stream = packet.stream
            if orig_stream not in self._streams:
                raise RuntimeError("Stream not found in PyavOutput")
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

            packet.stream = orig_stream
            self.outputtimestamp(timestamp)
