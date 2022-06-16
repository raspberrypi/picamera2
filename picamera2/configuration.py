from .controls import Controls

class Configuration:
    """
    A small wrapper class that can be used to turn our configuration dicts into real objects.
    The constructor can make an empty object, or initialise from a dict. There is also the
    make_dict() method which turns the object back into a dict.

    Derived classes should define:

    _ALLOWED_FIELDS: these are the only attributes that may be set, anything else will raise
        an error. The idea is to help prevent typos.

    _FIELD_CLASS_MAP: this allows you to turn a dict that we are given as a value (for some
        field) into a Configuration object. For example if someone is setting a dict into a
        field of a CameraConfiguration, you might want it to turn into a StreamConfiguration.

        One of these fields can be set by doing (for example) camera_config.lores = {}, which
        would be turned into a StreamConfiguration. Or for those averse to dicts, we allow
        camera_config.enable_lores() instead.

    _FORWARD_FIELDS: allows certain attribute names to be forwarded to another contained
        object. For example, if someone wants to set CameraConfiguration.size they probably
        mean to set CameraConfiguration.main.size. So it's a kind of helpful shorthand.
    """
    def __init__(self, d={}):
        if isinstance(d, Configuration):
            d = d.make_dict()
        for k in self._ALLOWED_FIELDS:
            self.__setattr__(k, None)
        for k, v in d.items():
            self.__setattr__(k, v)

    def __setattr__(self, name, value):
        if name in self._FORWARD_FIELDS:
            target = self._FORWARD_FIELDS[name]
            self.__getattribute__(target).__setattr__(name, value)
        elif name in self._ALLOWED_FIELDS:
            if name in self._FIELD_CLASS_MAP and isinstance(value, dict):
                value = self._FIELD_CLASS_MAP[name](value)
            super().__setattr__(name, value)
        else:
            raise RuntimeError(f"Invalid field '{name}'")

    def __getattribute__(self, name):
        prefix = "enable_"
        if name.startswith(prefix) and len(name) > len(prefix):
            field = name[len(prefix):]

            def func(onoff=True):
                if onoff:
                    self.__setattr__(field, {})
                else:
                    delattr(self, field)
            return func

        else:
            return super().__getattribute__(name)

    def __repr__(self):
        return type(self).__name__ + "(" + repr(self.make_dict()) + ")"

    def update(self, update_dict):
        for k, v in update_dict.items():
            self.__setattr__(k, v)

    def make_dict(self):
        d = {}
        for f in self._ALLOWED_FIELDS:
            if hasattr(self, f):
                value = getattr(self, f)
                if value is not None and f in self._FIELD_CLASS_MAP:
                    value = value.make_dict()
                d[f] = value
        return d

    def align(self, optimal=True):
        if optimal:
            # Adjust the image size so that all planes are a mutliple of 32 bytes wide.
            # This matches the hardware behaviour and means we can be more efficient.
            align = 32
            if self.format in ("YUV420", "YVU420"):
                align = 64  # because the UV planes will have half this alignment
            elif self.format in ("XBGR8888", "XRGB8888"):
                align = 16  # 4 channels per pixel gives us an automatic extra factor of 2
        else:
            align = 2
        self.size = (self.size[0] - self.size[0] % align, self.size[1] - self.size[1] % 2)


class StreamConfiguration(Configuration):
    _ALLOWED_FIELDS = ("size", "format", "stride", "framesize")
    _FIELD_CLASS_MAP = {}
    _FORWARD_FIELDS = {}


class CameraConfiguration(Configuration):
    def __make_controls__(controls):
        return Controls(CameraConfiguration.__picam2__, controls)

    _ALLOWED_FIELDS = ("use_case", "buffer_count", "transform", "display", "encode", "colour_space", "controls", "main", "lores", "raw")
    _FIELD_CLASS_MAP = {"main": StreamConfiguration, "lores": StreamConfiguration, "raw": StreamConfiguration, "controls": __make_controls__}
    _FORWARD_FIELDS = {"size": "main", "format": "main"}

    __picam2__ = None

    @staticmethod
    def set_picam2(picam2):
        CameraConfiguration.__picam2__ = picam2

    def align(self, optimal=True):
        self.main.align(optimal)
        if self.lores is not None:
            self.lores.align(optimal)
        # No sense trying to align the raw stream.
