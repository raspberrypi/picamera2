import fcntl

import v4l2

from .encoder import Encoder, Quality
from .jpeg_encoder import JpegEncoder
from .libav_h264_encoder import LibavH264Encoder
from .libav_mjpeg_encoder import LibavMjpegEncoder
from .multi_encoder import MultiEncoder

_hw_encoder_available = False
try:
    with open('/dev/video11', 'rb', buffering=0) as fd:
        caps = v4l2.v4l2_capability()
        fcntl.ioctl(fd, v4l2.VIDIOC_QUERYCAP, caps)
        _hw_encoder_available = (caps.card.decode('utf-8') == "bcm2835-codec-encode")
except Exception:
    pass

if _hw_encoder_available:
    from .h264_encoder import H264Encoder
else:
    from .libav_h264_encoder import LibavH264Encoder as H264Encoder

if _hw_encoder_available:
    from .mjpeg_encoder import MJPEGEncoder
else:
    from .libav_mjpeg_encoder import LibavMjpegEncoder as MJPEGEncoder
