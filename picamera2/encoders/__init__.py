import fcntl

import videodev2

from picamera2.platform import Platform, get_platform

from .encoder import Encoder, Quality
from .jpeg_encoder import JpegEncoder
from .libav_h264_encoder import LibavH264Encoder
from .libav_mjpeg_encoder import LibavMjpegEncoder
from .multi_encoder import MultiEncoder

_hw_encoder_available = get_platform() == Platform.VC4

if _hw_encoder_available:
    from .h264_encoder import H264Encoder
else:
    from .libav_h264_encoder import LibavH264Encoder as H264Encoder

if _hw_encoder_available:
    from .mjpeg_encoder import MJPEGEncoder
else:
    from .libav_mjpeg_encoder import LibavMjpegEncoder as MJPEGEncoder
