"""This is a base class for a multi-threaded software encoder."""

from fractions import Fraction
from math import sqrt

import av

from picamera2.encoders.encoder import Encoder, Quality

from ..request import MappedArray


class LibavH264Encoder(Encoder):
    """Encoder class that uses libx264 for h.264 encoding."""

    def __init__(self, bitrate=None, repeat=True, iperiod=30, framerate=30, qp=None, profile=None):
        """Initialise"""
        super().__init__()
        self._codec = "h264"  # for now only support h264
        self.repeat = repeat
        self.bitrate = bitrate
        self.iperiod = iperiod
        self.framerate = framerate
        self.qp = qp
        self.profile = profile
        self.preset = None

    def _setup(self, quality):
        # If an explicit quality was specified, use it, otherwise try to preserve any bitrate/qp
        # the user may have set for themselves.
        if quality is not None or \
           (getattr(self, "bitrate", None) is None and getattr(self, "qp", None) is None):
            quality = Quality.MEDIUM if quality is None else quality
            # These are suggested bitrates for 1080p30 in Mbps
            BITRATE_TABLE = {Quality.VERY_LOW: 3,
                             Quality.LOW: 4,
                             Quality.MEDIUM: 7,
                             Quality.HIGH: 10,
                             Quality.VERY_HIGH: 14}
            reference_complexity = 1920 * 1080 * 30
            actual_complexity = self.width * self.height * getattr(self, "framerate", 30)
            reference_bitrate = BITRATE_TABLE[quality] * 1000000
            self.bitrate = int(reference_bitrate * sqrt(actual_complexity / reference_complexity))

    def _start(self):
        self._container = av.open("/dev/null", "w", format="null")
        self._stream = self._container.add_stream(self._codec, rate=self.framerate)

        self._stream.codec_context.thread_count = 8
        self._stream.codec_context.thread_type = av.codec.context.ThreadType.FRAME  # noqa

        self._stream.width = self.width
        self._stream.height = self.height
        self._stream.pix_fmt = "yuv420p"

        preset = "ultrafast"
        if self.profile is not None:
            if not isinstance(self.profile, str):
                raise RuntimeError("Profile should be a string value")
            # Much more helpful to compare profile names case insensitively!
            available_profiles = {k.lower(): v for k, v in self._stream.codec.profiles.items()}
            profile = self.profile.lower()
            if profile not in available_profiles:
                raise RuntimeError("Profile " + self.profile + " not recognised")
            self._stream.codec_context.profile = available_profiles[profile]
            # The "ultrafast" preset always produces baseline, so:
            if "baseline" not in profile:
                preset = "superfast"

        if self.bitrate is not None:
            self._stream.codec_context.bit_rate = self.bitrate
        self._stream.codec_context.gop_size = self.iperiod

        # For those who know what they're doing, let them override the "preset".
        if self.preset:
            preset = self.preset
        self._stream.codec_context.options["preset"] = preset

        self._stream.codec_context.options["deblock"] = "1"
        # Absence of the "global header" flags means that SPS/PPS headers get repeated.
        if not self.repeat:
            self._stream.codec_context.flags |= av.codec.context.Flags.GLOBAL_HEADER  # noqa
        if self.qp is not None:
            self._stream.codec_context.qmin = self.qp
            self._stream.codec_context.qmax = self.qp

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
        with MappedArray(request, stream) as m:
            frame = av.VideoFrame.from_ndarray(m.array, format=self._av_input_format, width=self.width)
            frame.pts = timestamp_us
            for packet in self._stream.encode(frame):
                self.outputframe(bytes(packet), packet.is_keyframe, timestamp=packet.pts)
