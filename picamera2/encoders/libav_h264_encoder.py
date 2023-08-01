"""This is a base class for a multi-threaded software encoder."""

import av

from fractions import Fraction

from math import sqrt

from picamera2.encoders.encoder import Encoder, Quality
from ..request import MappedArray


class LibavH264Encoder(Encoder):
    """
    Encoder class that uses libx264 for h.264 encoding.
    """

    def __init__(self, bitrate=None, repeat=True, iperiod=30, framerate=30, qp=None):
        """Initialise
        """
        super().__init__()
        self._codec = "h264" # for now only support h264
        self.repeat = repeat
        self.bitrate = bitrate
        self.iperiod = iperiod
        self.framerate = framerate
        self._qp = qp

    def _setup(self, quality):
        if getattr(self, "bitrate", None) is None:
            # These are suggested bitrates for 1080p30 in Mbps
            BITRATE_TABLE = {Quality.VERY_LOW: 2,
                             Quality.LOW: 3,
                             Quality.MEDIUM: 5,
                             Quality.HIGH: 8,
                             Quality.VERY_HIGH: 12}
            reference_complexity = 1920 * 1080 * 30
            actual_complexity = self.width * self.height * self.framerate
            reference_bitrate = BITRATE_TABLE[quality] * 1000000
            self.bitrate = int(reference_bitrate * sqrt(actual_complexity / reference_complexity))

    def _start(self):
        self._container = av.open("/dev/null", "w", format="null")
        self._stream = self._container.add_stream(self._codec, rate=self.framerate)

        self._stream.codec_context.thread_count = 8
        self._stream.codec_context.thread_type = av.codec.context.ThreadType.FRAME

        self._stream.width = self.width
        self._stream.height = self.height
        self._stream.pix_fmt = "yuv420p"

        self._stream.codec_context.bit_rate = self.bitrate
        self._stream.codec_context.gop_size = self.iperiod
        self._stream.codec_context.options["preset"] = "ultrafast"
        self._stream.codec_context.options["deblock"] = "1"
        # Absence of the "global header" flags means that SPS/PPS headers get repeated.
        if not self.repeat:
            self._stream.codec_context.flags |= av.codec.context.Flags.GLOBAL_HEADER
        if self._qp is not None:
            self._stream.codec_context.qmin = self._qp
            self._stream.codec_context.qmax = self._qp

        self._stream.codec_context.time_base = Fraction(1, 1000000)

        FORMAT_TABLE = {"YUV420": "yuv420p",
                        "BGR888": "rgb24",
                        "RGB888": "bgr24",
                        "XBGR8888": "rgba",
                        "XRGB8888": "bgra"}
        self._av_input_format = FORMAT_TABLE[self._format]

    def _stop(self):
        for packet in self._stream.encode():
            self.outputframe(bytes(packet), packet.is_keyframe, timestamp=packet.pts)
        self._container.close()

    def _encode(self, stream, request):
        timestamp_us = self._timestamp(request)
        with MappedArray(request, self.name) as m:
            frame = av.VideoFrame.from_ndarray(m.array, format=self._av_input_format, width=self.width)
            frame.pts = timestamp_us
            for packet in self._stream.encode(frame):
                self.outputframe(bytes(packet), packet.is_keyframe, timestamp=packet.pts)
