"""MJPEG encoder functionality utilising V4L2"""

from v4l2 import *

from picamera2.encoders.v4l2_encoder import V4L2Encoder


class MJPEGEncoder(V4L2Encoder):
    """MJPEG encoder utilsing V4L2 functionality"""

    def __init__(self, bitrate):
        """Creates MJPEG encoder

        :param bitrate: Bitrate
        :type bitrate: int
        """
        super().__init__(bitrate, V4L2_PIX_FMT_MJPEG)
