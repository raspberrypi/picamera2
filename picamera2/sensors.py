from enum import Enum

# This file contains some utilities for finding out about sensors and manipulating
# the reported sensor modes.


class SensorMode(Enum):
    """Enum to enable selecting specific types of sensor mode."""
    FULL = 0
    BINNED = 1
    FAST = 2
    PREVIEW = 3
    _1080P = 4
    _720P = 5


def make_mode(format, size, crop, max_framerate, bit_depth):
    return {"format": format,
            "size": size,
            "crop": crop,
            "max_framerate": max_framerate,
            "bit_depth": bit_depth}


# We list all the mode details explicity as they are not all easily available. We're
# happy to merge pull requests for other libcamera-supported sensors that users have.
# There are two lists:
# defined_sensor_modes lists the actual modes that the driver provides, and
# recommended_sensor_modes maps a user's idea of the mode they want onto the ones
# that the driver actually has.

defined_sensor_modes = \
    {'imx219':
     {SensorMode.FULL:    make_mode('SBGGR10_CSI2P', (3280, 2464), (3280, 2464), 21.19,  10),
      SensorMode.BINNED:  make_mode('SBGGR10_CSI2P', (1640, 1232), (3280, 2464), 41.56,  10),
      SensorMode._1080P:  make_mode('SBGGR10_CSI2P', (1920, 1080), (1920, 1080), 41.85,  10),
      SensorMode.FAST:    make_mode('SBGGR10_CSI2P', (640, 480),   (1280, 960),  59.85,  10)},
     'imx477':
     {SensorMode.FULL:    make_mode('SBGGR12_CSI2P', (4056, 3040), (4056, 3040), 10.00,  12),
      SensorMode.BINNED:  make_mode('SBGGR12_CSI2P', (2028, 1520), (4056, 3040), 40.00,  12),
      SensorMode._1080P:  make_mode('SBGGR12_CSI2P', (2028, 1080), (4056, 2160), 50.02,  12),
      SensorMode.FAST:    make_mode('SBGGR10_CSI2P', (1332, 990),  (2664, 1980), 120.03, 10)},
     'ov5647':
     {SensorMode.FULL:    make_mode('SGBRG10_CSI2P', (2592, 1944), (2592, 1944), 15.63,  10),
      SensorMode.BINNED:  make_mode('SGBRG10_CSI2P', (1296, 972),  (2592, 1944), 43.25,  10),
      SensorMode._1080P:  make_mode('SGBRG10_CSI2P', (1920, 1080), (1920, 1080), 30.62,  10),
      SensorMode.FAST:    make_mode('SGBRG10_CSI2P', (640, 480),   (2560, 1920), 62.49,  10)}}

recommended_sensor_modes = \
    {'imx219':
     {SensorMode.FULL:    SensorMode.FULL,
      SensorMode.FAST:    SensorMode.FAST,
      SensorMode.PREVIEW: SensorMode.BINNED,
      SensorMode._1080P:  SensorMode._1080P,
      SensorMode._720P:   SensorMode.BINNED},
     'imx477':
     {SensorMode.FULL:    SensorMode.FULL,
      SensorMode.FAST:    SensorMode.FAST,
      SensorMode.PREVIEW: SensorMode.BINNED,
      SensorMode._1080P:  SensorMode._1080P,
      SensorMode._720P:   SensorMode._1080P},
     'ov5647':
     {SensorMode.FULL:    SensorMode.FULL,
      SensorMode.FAST:    SensorMode.FAST,
      SensorMode.PREVIEW: SensorMode.BINNED,
      SensorMode._1080P:  SensorMode._1080P,
      SensorMode._720P:   SensorMode.BINNED}}


def list_sensor_modes(sensor):
    """Return all the defined modes for a sensor."""
    if sensor not in defined_sensor_modes:
        raise RuntimeError(f"Sensor '{sensor}' not in sensor database")
    return defined_sensor_modes[sensor]


def get_sensor_mode(sensor, mode):
    """Return a suggested sensor mode."""
    return list_sensor_modes(sensor)[recommended_sensor_modes[sensor][mode]].copy()


class BayerOrder(Enum):
    """Enum to represet a specific Bayer order."""
    RGGB = 0
    GRBG = 1
    BGGR = 2
    GBRG = 3
    MONO = 4

    def hflip(self):
        """Horizontally flip the Bayer pattern."""
        return BayerOrder.MONO if self == BayerOrder.MONO else BayerOrder(self.value ^ 1)

    def vflip(self):
        """Vertically flip the Bayer pattern."""
        return BayerOrder.MONO if self == BayerOrder.MONO else BayerOrder(self.value ^ 2)


def make_sensor_format(format_string):
    """Utility to parse the libcamera sensor format string into useful parts."""
    parsed = {}
    for order in BayerOrder:
        if order.name in format_string:
            parsed['order'] = order
            break
    for bit_depth in (8, 10, 12, 14):
        if str(bit_depth) in format_string:
            parsed['bit_depth'] = bit_depth
            break
    parsed['packed'] = 'CSI2P' in format_string
    return parsed


def sensor_format_name(sensor_format):
    """Utility to turn a parsed sensor format into a libcamera sensor format string."""
    order = sensor_format['order'].name
    bit_depth = sensor_format['bit_depth']
    packed = '_CSI2P' if sensor_format['packed'] else ''
    return f"S{order}{bit_depth}{packed}"


def update_format_string(format_string, updates={}):
    """Update a sensor format string by overwriting some of its implied fields."""
    return sensor_format_name(make_sensor_format(format_string) | updates)


def update_sensor_mode_format(mode, format_updates={}):
    """Update the format string of a sensor mode by overwriting some of its implied fields."""
    mode['format'] = update_format_string(mode['format'], format_updates)
