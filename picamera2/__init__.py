import os
from concurrent.futures import TimeoutError

import libcamera

from .configuration import CameraConfiguration, StreamConfiguration
from .controls import Controls
from .converters import YUV420_to_RGB
from .job import CancelledError
from .metadata import Metadata
from .picamera2 import Picamera2, Preview
from .platform import Platform, get_platform
from .request import CompletedRequest, MappedArray
from .sensor_format import SensorFormat

if os.environ.get("XDG_SESSION_TYPE", None) == "wayland":
    # The code here works through the X wayland layer, but not otherwise.
    os.environ["QT_QPA_PLATFORM"] = "xcb"


def _set_configuration_file(filename):
    platform_dir = "vc4" if get_platform() == Platform.VC4 else "pisp"
    dirs = [
        os.path.expanduser(
            "~/libcamera/src/libcamera/pipeline/rpi/" + platform_dir + "/data"
        ),
        "/usr/local/share/libcamera/pipeline/rpi/" + platform_dir,
        "/usr/share/libcamera/pipeline/rpi/" + platform_dir]

    for directory in dirs:
        file = os.path.join(directory, filename)

        if os.path.isfile(file):
            os.environ['LIBCAMERA_RPI_CONFIG_FILE'] = file
            break


_set_configuration_file("rpi_apps.yaml")


def libcamera_transforms_eq(t1, t2):
    return t1.hflip == t2.hflip and t1.vflip == t2.vflip and t1.transpose == t2.transpose


def libcamera_colour_spaces_eq(c1, c2):
    return c1.primaries == c2.primaries and c1.transferFunction == c2.transferFunction and \
        c1.ycbcrEncoding == c2.ycbcrEncoding and c1.range == c2.range


libcamera.Transform.__repr__ = libcamera.Transform.__str__
libcamera.Transform.__eq__ = libcamera_transforms_eq

libcamera.ColorSpace.__repr__ = libcamera.ColorSpace.__str__
libcamera.ColorSpace.__eq__ = libcamera_colour_spaces_eq


def _libcamera_size_to_tuple(sz):
    return (sz.width, sz.height)


libcamera.Size.to_tuple = _libcamera_size_to_tuple


def _libcamera_rect_to_tuple(rect):
    return (rect.x, rect.y, rect.width, rect.height)


libcamera.Rectangle.to_tuple = _libcamera_rect_to_tuple
