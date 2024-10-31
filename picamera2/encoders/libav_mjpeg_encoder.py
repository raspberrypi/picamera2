"""This is a base class for a multi-threaded software encoder."""

from fractions import Fraction

import av

from picamera2.encoders.encoder import Encoder, Quality

from ..request import MappedArray


class LibavMjpegEncoder(Encoder):
    """Encoder class that uses libx264 for h.264 encoding."""

    def __init__(self, bitrate=None, repeat=True, iperiod=30, framerate=30, qp=None):
        """Initialise"""
        super().__init__()
        self._codec = "mjpeg"
        self.repeat = repeat
        self.bitrate = bitrate
        self.iperiod = iperiod
        self.framerate = framerate
        self.qp = qp

    def _setup(self, quality):
        # If an explicit quality was specified, use it, otherwise try to preserve any bitrate/qp
        # the user may have set for themselves.
        if quality is not None or \
           (getattr(self, "bitrate", None) is None and getattr(self, "qp", None) is None):
            quality = Quality.MEDIUM if quality is None else quality
            QP_TABLE = {Quality.VERY_LOW: 31,
                        Quality.LOW: 15,
                        Quality.MEDIUM: 10,
                        Quality.HIGH: 5,
                        Quality.VERY_HIGH: 3}
            self.qp = QP_TABLE[quality]

    def _start(self):
        self._container = av.open("/dev/null", "w", format="null")
        self._stream = self._container.add_stream(self._codec, rate=self.framerate)

        self._stream.codec_context.thread_count = 8
        self._stream.codec_context.thread_type = av.codec.context.ThreadType.FRAME

        self._stream.width = self.width
        self._stream.height = self.height
        self._stream.pix_fmt = "yuv420p"

        for out in self._output:
            out._add_stream(self._stream, self._codec, rate=self.framerate)

        # This is all rather arbitrary but comes out with a vaguely plausible a quantiser. I
        # found that the sqrt of the quantiser times the bitrate was approximately constant with
        # the value 64000000 for a 1080p30 stream, though obviously it will depend on content,
        # and probably the phase of the moon.
        if self.qp is None:
            reference_complexity = 1920 * 1080 * 30
            actual_complexity = self.width * self.height * getattr(self, "framerate", 30)
            reference_bitrate = self.bitrate * reference_complexity / actual_complexity
            self.qp = max(min(round(64000000 / reference_bitrate) ** 2, 127), 1)

        self._stream.codec_context.qmin = self.qp
        self._stream.codec_context.qmax = self.qp
        self._stream.codec_context.color_range = 2  # JPEG (full range)
        self._stream.codec_context.flags |= av.codec.context.Flags.QSCALE

        self._stream.codec_context.time_base = Fraction(1, 1000000)

        FORMAT_TABLE = {"YUV420": "yuv420p",
                        "BGR888": "rgb24",
                        "RGB888": "bgr24",
                        "XBGR8888": "rgba",
                        "XRGB8888": "bgra"}
        self._av_input_format = FORMAT_TABLE[self._format]

    def _stop(self):
        for packet in self._stream.encode():
            self.outputframe(bytes(packet), packet.is_keyframe, timestamp=packet.pts, packet=packet)
        self._container.close()

    def _encode(self, stream, request):
        timestamp_us = self._timestamp(request)
        with MappedArray(request, stream) as m:
            frame = av.VideoFrame.from_ndarray(m.array, format=self._av_input_format, width=self.width)
            frame.pts = timestamp_us
            for packet in self._stream.encode(frame):
                self.outputframe(bytes(packet), packet.is_keyframe, timestamp=packet.pts, packet=packet)
