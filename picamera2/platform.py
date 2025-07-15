import fcntl
import os
from enum import Enum

import videodev2


class Platform(Enum):
    VC4 = 0
    PISP = 1


_platform = Platform.VC4
try:
    for num in range(64):
        device = '/dev/video' + str(num)
        if os.path.exists(device):
            with open(device, 'rb+', buffering=0) as fd:
                caps = videodev2.v4l2_capability()
                fcntl.ioctl(fd, videodev2.VIDIOC_QUERYCAP, caps)
                decoded = videodev2.arr_to_str(caps.card)
                if decoded == "pispbe":
                    _platform = Platform.PISP
                    break
                elif decoded == "bcm2835-isp":
                    break
except Exception:
    pass


def get_platform():
    return _platform
