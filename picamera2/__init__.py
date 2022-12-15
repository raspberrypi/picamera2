from .configuration import CameraConfiguration, StreamConfiguration
from .controls import Controls
from .converters import YUV420_to_RGB
from .metadata import Metadata
from .picamera2 import Picamera2, Preview
from .request import CompletedRequest, MappedArray

import libcamera


def libcamera_transforms_eq(t1, t2):
    return (
        t1.hflip == t2.hflip and t1.vflip == t2.vflip and t1.transpose == t2.transpose
    )


def libcamera_colour_spaces_eq(c1, c2):
    return (
        c1.primaries == c2.primaries
        and c1.transferFunction == c2.transferFunction
        and c1.ycbcrEncoding == c2.ycbcrEncoding
        and c1.range == c2.range
    )


libcamera.Transform.__repr__ = libcamera.Transform.__str__
libcamera.Transform.__eq__ = libcamera_transforms_eq

libcamera.ColorSpace.__repr__ = libcamera.ColorSpace.__str__
libcamera.ColorSpace.__eq__ = libcamera_colour_spaces_eq
