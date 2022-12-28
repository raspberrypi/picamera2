import sys

sys.path.append("/usr/lib/python3/dist-packages")
import libcamera

from picamera2.configuration import CameraConfiguration, StreamConfiguration
from picamera2.controls import Controls
from picamera2.converters import YUV420_to_RGB
from picamera2.lc_helpers import libcamera_color_spaces_eq, libcamera_transforms_eq
from picamera2.metadata import Metadata
from picamera2.picamera2 import CameraInfo, Picamera2
from picamera2.request import CompletedRequest

# NOTE(meawoppl) - ugleeee monkey patch. Kill the below VV
libcamera.Transform.__repr__ = libcamera.Transform.__str__
libcamera.Transform.__eq__ = libcamera_transforms_eq

libcamera.ColorSpace.__repr__ = libcamera.ColorSpace.__str__
libcamera.ColorSpace.__eq__ = libcamera_color_spaces_eq


__all__ = [
    "CameraConfiguration",
    "StreamConfiguration",
    "Controls",
    "YUV420_to_RGB",
    "Metadata",
    "Picamera2",
    "CameraInfo",
    "CompletedRequest",
]
