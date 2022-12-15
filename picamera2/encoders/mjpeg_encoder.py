"""MJPEG encoder functionality utilising V4L2"""

from math import sqrt

from v4l2 import V4L2_PIX_FMT_MJPEG

from picamera2.encoders import Quality
from picamera2.encoders.v4l2_encoder import V4L2Encoder


class MJPEGEncoder(V4L2Encoder):
    """MJPEG encoder utilsing V4L2 functionality"""

    def __init__(self, bitrate=None):
        """Creates MJPEG encoder

        :param bitrate: Bitrate, default None
        :type bitrate: int
        """
        super().__init__(bitrate, V4L2_PIX_FMT_MJPEG)

    def _setup(self, quality):
        if self._requested_bitrate is None:
            # These are suggested bitrates for 1080p30 in Mbps
            BITRATE_TABLE = {
                Quality.VERY_LOW: 6,
                Quality.LOW: 12,
                Quality.MEDIUM: 18,
                Quality.HIGH: 27,
                Quality.VERY_HIGH: 45,
            }
            reference_complexity = 1920 * 1080 * 30
            actual_complexity = self.width * self.height * self.framerate
            reference_bitrate = BITRATE_TABLE[quality] * 1000000
            self._bitrate = int(
                reference_bitrate * sqrt(actual_complexity / reference_complexity)
            )
        else:
            self._bitrate = self._requested_bitrate
