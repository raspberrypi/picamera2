from picamera2.encoders.v4l2_encoder import V4L2Encoder
from v4l2 import *


class H264Encoder(V4L2Encoder):
    def __init__(self, bitrate, repeat=False, iperiod=None):
        super().__init__(bitrate, V4L2_PIX_FMT_H264)
        if iperiod is not None:
            self._controls += [(V4L2_CID_MPEG_VIDEO_H264_I_PERIOD, iperiod)]
        if repeat:
            self._controls += [(V4L2_CID_MPEG_VIDEO_REPEAT_SEQ_HEADER, 1)]
