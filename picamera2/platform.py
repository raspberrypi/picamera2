from enum import Enum
import fcntl
import v4l2

class Platform(Enum):
    VC4 = 0
    PISP = 1

_platform = Platform.VC4
try:
    with open('/dev/video0', 'rb+', buffering=0) as fd:
        caps = v4l2.v4l2_capability()
        fcntl.ioctl(fd, v4l2.VIDIOC_QUERYCAP, caps)
        if caps.card.decode('utf-8') == "rp1-cfe":
            _platform = Platform.PISP
except Exception as e:
    pass

def get_platform():
    return _platform
