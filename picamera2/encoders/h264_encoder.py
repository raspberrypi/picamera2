"""H264 encoder functionality"""

from v4l2 import (V4L2_CID_MPEG_VIDEO_H264_I_PERIOD,
                  V4L2_CID_MPEG_VIDEO_H264_LEVEL,
                  V4L2_CID_MPEG_VIDEO_H264_MAX_QP,
                  V4L2_CID_MPEG_VIDEO_H264_MIN_QP,
                  V4L2_CID_MPEG_VIDEO_H264_PROFILE,
                  V4L2_CID_MPEG_VIDEO_REPEAT_SEQ_HEADER,
                  V4L2_MPEG_VIDEO_H264_LEVEL_4_1,
                  V4L2_MPEG_VIDEO_H264_LEVEL_4_2,
                  V4L2_MPEG_VIDEO_H264_PROFILE_BASELINE,
                  V4L2_MPEG_VIDEO_H264_PROFILE_CONSTRAINED_BASELINE,
                  V4L2_MPEG_VIDEO_H264_PROFILE_HIGH,
                  V4L2_MPEG_VIDEO_H264_PROFILE_MAIN, V4L2_PIX_FMT_H264)

from picamera2.encoders import Quality
from picamera2.encoders.v4l2_encoder import V4L2Encoder


class H264Encoder(V4L2Encoder):
    """Uses functionality from V4L2Encoder"""

    def __init__(self, bitrate=None, repeat=True, iperiod=None, framerate=None, enable_sps_framerate=False,
                 qp=None, profile=None):
        """H264 Encoder

        :param bitrate: Bitrate, default None
        :type bitrate: int
        :param repeat: Repeat seq header, defaults to True
        :type repeat: bool, optional
        :param iperiod: Iperiod, defaults to None
        :type iperiod: int, optional
        :param framerate: record a framerate in the stream (whether true or not)
        :type framerate: float, optional
        :param qp: Fixed quantiser from 1 to 51 (disables constant bitrate), default None
        :type qp: int
        """
        super().__init__(bitrate, V4L2_PIX_FMT_H264)
        self.iperiod = iperiod
        self.repeat = repeat
        self.qp = qp
        self.profile = profile
        # The framerate can be reported in the sequence headers if enable_sps_framerate is set,
        # but there's no guarantee that frames will be delivered to the codec at that rate!
        self.framerate = framerate
        self._enable_framerate = enable_sps_framerate

    def _start(self):
        self._controls = []

        # These names match what FFmpeg uses.
        profile_lookup = {"baseline": V4L2_MPEG_VIDEO_H264_PROFILE_BASELINE,
                          "constrained baseline": V4L2_MPEG_VIDEO_H264_PROFILE_CONSTRAINED_BASELINE,
                          "main": V4L2_MPEG_VIDEO_H264_PROFILE_MAIN,
                          "high": V4L2_MPEG_VIDEO_H264_PROFILE_HIGH}
        if self.profile:
            if not isinstance(self.profile, str):
                raise RuntimeError("Profile should be a string value")
            profile = self.profile.lower()
            if profile in profile_lookup:
                self._controls += [(V4L2_CID_MPEG_VIDEO_H264_PROFILE, profile_lookup[profile])]
            else:
                raise RuntimeError("Profile " + self.profile + " not recognised")
        if self.iperiod is not None:
            self._controls += [(V4L2_CID_MPEG_VIDEO_H264_I_PERIOD, self.iperiod)]
        if self.repeat:
            self._controls += [(V4L2_CID_MPEG_VIDEO_REPEAT_SEQ_HEADER, 1)]

        codec_level = 40
        # We may need to up the codec level to 4.2 if we have a guidance framerate and the
        # required macroblocks per second is too high.
        if self.framerate is not None:
            mbs_per_sec = ((self._width + 15) // 16) * ((self._height + 15) // 16) * self.framerate
            if mbs_per_sec > 245760:
                self._controls += [(V4L2_CID_MPEG_VIDEO_H264_LEVEL, V4L2_MPEG_VIDEO_H264_LEVEL_4_2)]
                codec_level = 42

        # If the bitrate is > 10Mbps then the level must be at least 4.1
        if self.bitrate is not None and self.bitrate > 10000000 and codec_level == 40:
            self._controls += [(V4L2_CID_MPEG_VIDEO_H264_LEVEL, V4L2_MPEG_VIDEO_H264_LEVEL_4_1)]
            codec_level = 41

        if self.qp is not None:
            self._controls += [(V4L2_CID_MPEG_VIDEO_H264_MIN_QP, self.qp)]
            self._controls += [(V4L2_CID_MPEG_VIDEO_H264_MAX_QP, self.qp)]

        # The output objects may need to know what kind of stream this is.
        for out in self._output:
            out._add_stream("video", "h264")

        super()._start()

    def _setup(self, quality):
        # If an explicit quality was specified, use it, otherwise try to preserve any bitrate/qp
        # the user may have set for themselves.
        if quality is not None or \
           (getattr(self, "bitrate", None) is None and getattr(self, "qp", None) is None):
            quality = Quality.MEDIUM if quality is None else quality
            # These are suggested bitrates for 1080p30 in Mbps
            BITRATE_TABLE = {Quality.VERY_LOW: 2,
                             Quality.LOW: 4,
                             Quality.MEDIUM: 6,
                             Quality.HIGH: 9,
                             Quality.VERY_HIGH: 15}
            reference_complexity = 1920 * 1080 * 30
            actual_complexity = self.width * self.height * getattr(self, "framerate", 30)
            reference_bitrate = BITRATE_TABLE[quality] * 1000000
            self.bitrate = int(reference_bitrate * actual_complexity / reference_complexity)
