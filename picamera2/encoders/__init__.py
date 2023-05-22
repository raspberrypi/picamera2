import fcntl
import v4l2

_h264_hw_encoder_available = False
try:
    with open('/dev/video11', 'rb', buffering=0) as fd:
        caps = v4l2.v4l2_capability()
        fcntl.ioctl(fd, v4l2.VIDIOC_QUERYCAP, caps)
        _hw_encoder_available = (caps.card.decode('utf-8') == "bcm2835-codec-encode")
except Exception as e:
    pass

from .encoder import Encoder, Quality
if _h264_hw_encoder_available:
    from .h264_encoder import H264Encoder
else:
    from .libav_encoder import LibavEncoder as H264Encoder
from .jpeg_encoder import JpegEncoder
from .mjpeg_encoder import MJPEGEncoder
from .multi_encoder import MultiEncoder
from .libav_encoder import LibavEncoder
