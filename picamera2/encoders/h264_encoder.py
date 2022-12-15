"""H264 encoder functionality"""

from math import sqrt

from v4l2 import (
    V4L2_CID_MPEG_VIDEO_H264_I_PERIOD,
    V4L2_CID_MPEG_VIDEO_REPEAT_SEQ_HEADER,
    V4L2_PIX_FMT_H264,
)

from picamera2.encoders import Quality
from picamera2.encoders.v4l2_encoder import V4L2Encoder


class H264Encoder(V4L2Encoder):
    """Uses functionality from V4L2Encoder"""

    def __init__(self, bitrate=None, repeat=True, iperiod=None):
        """H264 Encoder

        :param bitrate: Bitrate, default None
        :type bitrate: int
        :param repeat: Repeat seq header, defaults to True
        :type repeat: bool, optional
        :param iperiod: Iperiod, defaults to None
        :type iperiod: int, optional
        """
        super().__init__(bitrate, V4L2_PIX_FMT_H264)
        if iperiod is not None:
            self._controls += [(V4L2_CID_MPEG_VIDEO_H264_I_PERIOD, iperiod)]
        if repeat:
            self._controls += [(V4L2_CID_MPEG_VIDEO_REPEAT_SEQ_HEADER, 1)]

    def _setup(self, quality):
        if self._requested_bitrate is None:
            # These are suggested bitrates for 1080p30 in Mbps
            BITRATE_TABLE = {
                Quality.VERY_LOW: 2,
                Quality.LOW: 4,
                Quality.MEDIUM: 6,
                Quality.HIGH: 9,
                Quality.VERY_HIGH: 15,
            }
            reference_complexity = 1920 * 1080 * 30
            actual_complexity = self.width * self.height * self.framerate
            reference_bitrate = BITRATE_TABLE[quality] * 1000000
            self._bitrate = int(
                reference_bitrate * sqrt(actual_complexity / reference_complexity)
            )
        else:
            self._bitrate = self._requested_bitrate
