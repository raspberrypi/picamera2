import sys

sys.path.append("/usr/lib/python3/dist-packages")
import libcamera

from scicamera.camera import Camera, CameraInfo
from scicamera.configuration import CameraConfig, StreamConfig
from scicamera.controls import Controls
from scicamera.converters import YUV420_to_RGB
from scicamera.lc_helpers import libcamera_color_spaces_eq, libcamera_transforms_eq
from scicamera.request import CompletedRequest

# NOTE(meawoppl) - ugleeee monkey patch. Kill the below VV
libcamera.Transform.__repr__ = libcamera.Transform.__str__
libcamera.Transform.__eq__ = libcamera_transforms_eq

libcamera.ColorSpace.__repr__ = libcamera.ColorSpace.__str__
libcamera.ColorSpace.__eq__ = libcamera_color_spaces_eq


__all__ = [
    "CameraConfig",
    "StreamConfig",
    "Controls",
    "YUV420_to_RGB",
    "Camera",
    "CameraInfo",
    "CompletedRequest",
]
