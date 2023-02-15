from libcamera import ColorSpace, Rectangle, Size

import picamera2.formats as formats


def convert_from_libcamera_type(value):
    if isinstance(value, Rectangle):
        value = (value.x, value.y, value.width, value.height)
    elif isinstance(value, Size):
        value = (value.width, value.height)
    elif isinstance(value, list) and all(isinstance(item, Rectangle) for item in value):
        value = [(v.x, v.y, v.width, v.height) for v in value]
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
