from picamera2 import formats
from picamera2.sensor_format import SensorFormat


def align_stream(stream_config: dict, optimal=True) -> None:
    if optimal:
        # Adjust the image size so that all planes are a mutliple of 32 bytes wide.
        # This matches the hardware behaviour and means we can be more efficient.
        align = 32
        if stream_config["format"] in ("YUV420", "YVU420"):
            align = 64  # because the UV planes will have half this alignment
        elif stream_config["format"] in ("XBGR8888", "XRGB8888"):
            align = 16  # 4 channels per pixel gives us an automatic extra factor of 2
    else:
        align = 2
    size = stream_config["size"]
    stream_config["size"] = (size[0] - size[0] % align, size[1] - size[1] % 2)


def align_configuration(config: dict, optimal=True) -> None:
    align_stream(config["main"], optimal=optimal)
    if "lores" in config and config["lores"] is not None:
        align_stream(config["lores"], optimal=optimal)
    # No point aligning the raw stream, it wouldn't mean anything.


def make_initial_stream_config(
    stream_config: dict, updates: dict, ignore_list=[]
) -> dict:
    """Take an initial stream_config and add any user updates.

    :param stream_config: Stream configuration
    :type stream_config: dict
    :param updates: Updates
    :type updates: dict
    :raises ValueError: Invalid key
    :return: Dictionary of stream config
    :rtype: dict
    """
    if updates is None:
        return None
    valid = ("format", "size")
    for key, value in updates.items():
        if isinstance(value, SensorFormat):
            value = str(value)
        if key in valid:
            stream_config[key] = value
        elif key in ignore_list:
            pass  # allows us to pass items from the sensor_modes as a raw stream
        else:
            raise ValueError(
                f"Bad key '{key}': valid stream configuration keys are {valid}"
            )
    return stream_config


# TODO(meawoppl) - dataclass __post_init__ materials
def check_stream_config(stream_config, name) -> None:
    """Check the configuration of the passed in config.

    Raises RuntimeError if the configuration is invalid.
    """
    # Check the parameters for a single stream.
    if type(stream_config) is not dict:
        raise RuntimeError(name + " stream should be a dictionary")
    if "format" not in stream_config:
        raise RuntimeError("format not found in " + name + " stream")
    if "size" not in stream_config:
        raise RuntimeError("size not found in " + name + " stream")
    format = stream_config["format"]
    if type(format) is not str:
        raise RuntimeError("format in " + name + " stream should be a string")
    if name == "raw":
        if not formats.is_raw(format):
            raise RuntimeError("Unrecognized raw format " + format)
    else:
        # Allow "MJPEG" as we have some support for USB MJPEG-type cameras.
        if (
            not formats.is_YUV(format)
            and not formats.is_RGB(format)
            and format != "MJPEG"
        ):
            raise RuntimeError("Bad format " + format + " in stream " + name)
    size = stream_config["size"]
    if type(size) is not tuple or len(size) != 2:
        raise RuntimeError("size in " + name + " stream should be (width, height)")
    if size[0] % 2 or size[1] % 2:
        raise RuntimeError("width and height should be even")
