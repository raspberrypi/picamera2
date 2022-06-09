from v4l2 import *

from picamera2.encoders.v4l2_encoder import V4L2Encoder


class MJPEGEncoder(V4L2Encoder):
    def __init__(self, bitrate):
        super().__init__(bitrate, V4L2_PIX_FMT_MJPEG)
