"""This is a base class for a multi-threaded software encoder."""

import time
from fractions import Fraction
from math import sqrt

import av

import picamera2.platform as Platform
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
        self.drop_final_frames = False
        self.threads = 0  # means "you choose"
        self._lasttimestamp = None
        self._use_hw = False

    @property
    def use_hw(self):
        """Whether hardware encode will be used (can be set to True only for VC4 platforms)."""
        return self._use_hw

    @use_hw.setter
    def use_hw(self, value):
        """Set this property in order to get libav to use the V4L2 hardware encoder (VC4 platforms only)."""
        if value:
            if Platform.get_platform() == Platform.Platform.VC4:
                self._use_hw = True
                self._codec = "h264_v4l2m2m"
            else:
                print("Warning: use_hw has no effect on non-VC4 platforms")

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

        self._stream.codec_context.thread_count = self.threads
        self._stream.codec_context.thread_type = av.codec.context.ThreadType.FRAME  # noqa

        self._stream.width = self.width
        self._stream.height = self.height
        self._stream.pix_fmt = "yuv420p"

        for out in self._output:
            out._add_stream(self._stream, self._codec, rate=self.framerate)

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
        self._stream.codec_context.options["tune"] = "zerolatency"

        FORMAT_TABLE = {"YUV420": "yuv420p",
                        "BGR888": "rgb24",
                        "RGB888": "bgr24",
                        "XBGR8888": "rgba",
                        "XRGB8888": "bgra"}
        self._av_input_format = FORMAT_TABLE[self._format]

    def _stop(self):
        if not self.drop_final_frames:
            # Annoyingly, libav still has lots of encoded frames internally which we must flush
            # out. If the output(s) doesn't understand timestamps, we may need to "pace" these
            # frames with correct time intervals. Unpleasant.
            for packet in self._stream.encode():
                if any(out.needs_pacing for out in self._output) and self._lasttimestamp is not None:
                    time_system, time_packet = self._lasttimestamp
                    delay_us = packet.pts - time_packet - (time.monotonic_ns() - time_system) / 1000
                    if delay_us > 0:
                        time.sleep(delay_us / 1000000)
                self._lasttimestamp = (time.monotonic_ns(), packet.pts)
                self.outputframe(bytes(packet), packet.is_keyframe, timestamp=packet.pts, packet=packet)
        self._container.close()

    def _encode(self, stream, request):
        timestamp_us = self._timestamp(request)
        with MappedArray(request, stream) as m:
            frame = av.VideoFrame.from_ndarray(m.array, format=self._av_input_format, width=self.width)
            frame.pts = timestamp_us
            for packet in self._stream.encode(frame):
                self._lasttimestamp = (time.monotonic_ns(), packet.pts)
                self.outputframe(bytes(packet), packet.is_keyframe, timestamp=packet.pts, packet=packet)
