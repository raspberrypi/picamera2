from typing import Any, Dict

import libcamera


def _convert_from_libcamera_type(value):
    if isinstance(value, libcamera.Rectangle):
        value = (value.x, value.y, value.width, value.height)
    elif isinstance(value, libcamera.Size):
        value = (value.width, value.height)
    return value


def lc_unpack(lc_dict) -> Dict[str, Any]:
    unpacked = {}
    for k, v in lc_dict.items():
        unpacked[k.name] = _convert_from_libcamera_type(v)
    return unpacked


def lc_unpack_controls(lc_dict) -> Dict[str, Any]:
    unpacked = {}
    for k, v in lc_dict.items():
        unpacked[k.name] = (k, v)
    return unpacked


LCTransform = libcamera._libcamera.Transform


def libcamera_transforms_eq(t1: LCTransform, t2: LCTransform) -> bool:
    """Return ``True`` if the two transforms are equivalent."""
    return (
        t1.hflip == t2.hflip and t1.vflip == t2.vflip and t1.transpose == t2.transpose
    )


def libcamera_color_spaces_eq(c1, c2) -> bool:
    """Return ``True`` if the two color spaces are equivalent."""
    return (
        c1.primaries == c2.primaries
        and c1.transferFunction == c2.transferFunction
        and c1.ycbcrEncoding == c2.ycbcrEncoding
        and c1.range == c2.range
    )
