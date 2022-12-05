from libcamera import Rectangle, Size


def convert_from_libcamera_type(value):
    if isinstance(value, Rectangle):
        value = (value.x, value.y, value.width, value.height)
    elif isinstance(value, Size):
        value = (value.width, value.height)
    return value
