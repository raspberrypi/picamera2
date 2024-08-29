import fcntl
import os
from enum import Enum

import v4l2


class Platform(Enum):
    VC4 = 0
    PISP = 1


_platform = Platform.VC4
try:
    for num in range(64):
        device = '/dev/video' + str(num)
        if os.path.exists(device):
            with open(device, 'rb+', buffering=0) as fd:
                caps = v4l2.v4l2_capability()
                fcntl.ioctl(fd, v4l2.VIDIOC_QUERYCAP, caps)
                decoded = caps.card.decode('utf-8')
                if decoded == "pispbe":
                    _platform = Platform.PISP
                    break
                elif decoded == "bcm2835-isp":
                    break
except Exception:
    pass


def get_platform():
    return _platform
