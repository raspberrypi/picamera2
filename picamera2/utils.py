from libcamera import ColorSpace, Orientation, Rectangle, Size, Transform

import picamera2.formats as formats


def convert_from_libcamera_type(value):
    if isinstance(value, Rectangle):
        value = value.to_tuple()
    elif isinstance(value, Size):
        value = value.to_tuple()
    elif isinstance(value, (list, tuple)) and all(isinstance(item, Rectangle) for item in value):
        value = [v.to_tuple() for v in value]
    return value


def colour_space_to_libcamera(colour_space, format):
    # libcamera may complain if we supply an RGB format stream with a YCbCr matrix or range.
    if formats.is_RGB(format):
        colour_space = ColorSpace(colour_space)  # it could be shared with other streams, so copy it
        colour_space.ycbcrEncoding = ColorSpace.YcbcrEncoding.Null
        colour_space.range = ColorSpace.Range.Full
    return colour_space


COLOUR_SPACE_TABLE = {ColorSpace.Sycc(), ColorSpace.Smpte170m(), ColorSpace.Rec709()}


def colour_space_from_libcamera(colour_space):
    # Colour spaces may come back from libcamera without a YCbCr matrix or range, meaning
    # they don't look like the 3 standard colour spaces (in the table) that we expect people
    # to use. Let's fix that.
    if colour_space is None:  # USB webcams might have a "None" colour space
        return None
    for cs in COLOUR_SPACE_TABLE:
        if colour_space.primaries == cs.primaries and colour_space.transferFunction == cs.transferFunction:
            return cs
    return colour_space


_TRANSFORM_TO_ORIENTATION_TABLE = {
    Transform(): Orientation.Rotate0,
    Transform(hflip=1): Orientation.Rotate0Mirror,
    Transform(vflip=1): Orientation.Rotate180Mirror,
    Transform(hflip=1, vflip=1): Orientation.Rotate180,
    Transform(transpose=1): Orientation.Rotate90Mirror,
    Transform(transpose=1, hflip=1): Orientation.Rotate270,
    Transform(transpose=1, vflip=1): Orientation.Rotate90,
    Transform(transpose=1, hflip=1, vflip=1): Orientation.Rotate270Mirror
}

_ORIENTATION_TO_TRANSFORM_TABLE = {
    Orientation.Rotate0: Transform(),
    Orientation.Rotate0Mirror: Transform(hflip=1),
    Orientation.Rotate180Mirror: Transform(vflip=1),
    Orientation.Rotate180: Transform(hflip=1, vflip=1),
    Orientation.Rotate90Mirror: Transform(transpose=1),
    Orientation.Rotate270: Transform(transpose=1, hflip=1),
    Orientation.Rotate90: Transform(transpose=1, vflip=1),
    Orientation.Rotate270Mirror: Transform(transpose=1, hflip=1, vflip=1)
}


def transform_to_orientation(transform):
    # A transform is an object and not a proper dictionary key, so must search by hand.
    if isinstance(transform, Transform):
        for k, v in _TRANSFORM_TO_ORIENTATION_TABLE.items():
            if k == transform:
                return v
    raise RuntimeError(f"Unknown transform {transform}")


def orientation_to_transform(orientation):
    # Return a copy of the object.
    return Transform(_ORIENTATION_TO_TRANSFORM_TABLE[orientation])
