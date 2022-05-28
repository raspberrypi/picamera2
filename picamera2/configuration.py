import libcamera

# Libcamera role objects.
STILL = libcamera.StreamRole.StillCapture
RAW = libcamera.StreamRole.Raw
VIDEO = libcamera.StreamRole.VideoRecording
VIEWFINDER = libcamera.StreamRole.Viewfinder

# Libcamera colorspace objects.
COLORSPACE_JPEG = libcamera.ColorSpace.Jpeg()
COLORSPACE_SMPTE170M = libcamera.ColorSpace.Smpte170m()
COLORSPACE_REC709 = libcamera.ColorSpace.Rec709()
COLORSPACE_SRGB = libcamera.ColorSpace.Srgb()
COLORSPACE_REC2020 = libcamera.ColorSpace.Rec2020()
COLORSPACE_RAW = libcamera.ColorSpace.Raw()


class StreamOptions():
    """
    This class uses libcamera to estimate valid stream configuration options.
    These options are then assigned as class instance attributes and are
    used by the configura libcamera function.

    """
    def __init__(self, name, *opts_args, **opts_keywords):
        self._setup_stream_names(name)
        self._set_stream_and_dtypes()
        self.role = None
        user_opts = check_args(opts_args, opts_keywords)
        if user_opts is not False:
            other_opts = ['name', 'display_name', 'encode_name', 'role']
            for opt, val in user_opts.items():
                if (opt not in self.__stream_options and opt not in other_opts):
                    raise KeyError(f"{opt} not a valid Stream option.")
                if opt not in other_opts:
                    dtype = self.__stream_options[opt]
                    if not isinstance(val, self.__stream_options[opt]):
                        raise ValueError(f"{opt} must be {dtype}")
                setattr(self, opt, val)

    def _setup_stream_names(self, name):
        self.name = self.display_name = self.encode_name = str(name)
        valid_names = ['main', 'lores', 'raw']
        if self.name not in valid_names:
            raise ValueError(f"Stream name must be in {valid_names}.")

    def _set_stream_and_dtypes(self):

        # Use Libcamera to get the options for each stream.
        drops = ['stream', 'formats']
        opts = [opt for opt in libcamera.StreamConfiguration.__dict__.keys()
                if '__' not in opt and opt not in drops]

        # Assign dtypes to stream options.
        self.__stream_options = {}
        for opt in opts:
            setattr(self, opt, None)
            if opt == 'color_space':
                self.__stream_options[opt] = (libcamera.ColorSpace, type(None))
            elif opt in ['stride,frame_size', 'buffer_count']:
                self.__stream_options[opt] = (int, float, type(None))
            elif opt == 'size':
                self.__stream_options[opt] = (list, tuple, type(None))
            elif opt == 'pixel_format':
                self.__stream_options[opt] = (str, type(None))
            else:
                self.__stream_options[opt] = (int, float, list, tuple,
                                              str, libcamera.ColorSpace, type(None))

    @property
    def _libcamera_options(self) -> dict:
        """
        This is a read-only function intended for libcamera internal use only.
        """
        cfg = {}
        for opt, dtypes in self.__stream_options.items():
            val = getattr(self, opt)  # Get user defined options.
            if not isinstance(val, dtypes):  # If the user supplied the wrong type...
                raise TypeError(f"{opt} must be {dtypes}.")
            cfg[opt] = val
        cfg = {k: v for k, v in cfg.items() if v is not None}  # Drop nones
        return cfg

    @property
    def config(self) -> dict:
        """
        This is a read-only function intended to show users what configuration
        they issued.
        """
        cfg = {'display_name': self.display_name,
               'encode_name': self.encode_name,
               'role': self.role} | self._libcamera_options
        return cfg


class TransformOptions():
    def __init__(self, *opts_args, **opts_keywords):

        # Establish available transform options.
        self._set_transform_and_dtypes()

        # Apply user supplied options, if any.
        user_opts = check_args(opts_args, opts_keywords)
        if user_opts is not False:
            for opt, val in user_opts.items():
                if opt not in list(self.__transform_options.keys()):
                    raise KeyError(f"{opt} is not a valid Transform option.")
                if not isinstance(val, self.__transform_options[opt]):
                    raise ValueError(f"{opt} must be an int, float, or bool.")
                setattr(self, opt, val)

    def _set_transform_and_dtypes(self):
        _transforms = [opt for opt in dir(libcamera.Transform)
                       if '__' not in opt]
        self.__transform_options = {}
        for transform in _transforms:
            setattr(self, transform, None)
            self.__transform_options[transform] = (int, float, bool, type(None))

    @property
    def _libcamera_options(self) -> dict:
        cfg = {}  # Create a holder for values to be applied.
        for opt, dtypes in self.__transform_options.items():
            val = getattr(self, opt)
            if not isinstance(val, dtypes):
                raise ValueError(f"{opt} must have a type of {dtypes}.")
            else:
                cfg[opt] = val

        # Drop entries with None so that libcamera doesn't receive them.
        cfg = {k: v for k, v in cfg.items() if v is not None}
        return cfg

    @property
    def config(self) -> dict:
        return self._libcamera_options


class ControlOptions():
    def __init__(self, camera_num=0, *opts_args, **opts_keywords):

        # Get a list of controls from the camera.
        ctrls = libcamera.CameraManager.singleton().cameras[camera_num].controls

        # Apply controls to this class instance.
        for ctrl, val in ctrls.items():  # Get list of controls from the camera.
            setattr(self, ctrl, None)  # Set all to None initially.

        self._set_control_types(ctrls)
        opts = check_args(opts_args, opts_keywords)
        if opts is not False:
            for ctrl, val in opts.items():
                if ctrl not in ctrls.keys():
                    raise KeyError(f"{ctrl} not a valid camera control.")
                setattr(self, ctrl, val)

    def _set_control_types(self, ctrls_from_camera):
        """This function estimates the valid input types for each control based
        on what the camera returns for controls. Additional type options are
        also included."""
        self._ctrl_types = {k: type(v[-1]) for k, v in ctrls_from_camera.items()}
        for c, t in self._ctrl_types.items():  # For control, type
            if t is tuple:
                try:
                    self._ctrl_types[c] = (tuple, list, getattr(libcamera, c),
                                           type(None))
                except:
                    self._ctrl_types[c] = (tuple, list, type(None))
            elif t is float:
                try:
                    self._ctrl_types[c] = (float, int, getattr(libcamera, c),
                                           type(None))
                except:
                    self._ctrl_types[c] = (float, int, type(None))
            elif (t is int and
                  c in ['FrameDurationLimits', 'ColourCorrectionMatrix']):
                self._ctrl_types[c] = (tuple, list, type(None))
            elif t is int:
                try:
                    self._ctrl_types[c] = (int, getattr(libcamera, c), type(None))
                except:
                    self._ctrl_types[c] = (int, type(None))

    @property
    def _libcamera_options(self) -> dict:
        """
        This is a read-only function for picamera2 functions that
        configure libcamera internally.
        """
        controls = {}
        for ctrl, _types in self._ctrl_types.items():
            val = getattr(self, ctrl)
            if not isinstance(val, _types):
                raise TypeError
            controls[ctrl] = val
        controls = {k: v for k, v in controls.items() if v is not None}
        return controls

    @property
    def config(self):
        """
        This is a read-only function intended to show users what configuration
        they issued.
        """
        return self._libcamera_options


class CameraOptions():
    """This is an overarching class that compiles all camera configuration
    options in a single place for the user. Those looking to create a custom
    configuration function should use this."""

    transform: (TransformOptions, dict)
    main: (StreamOptions, dict)
    lores: (StreamOptions, dict)
    raw: (StreamOptions, dict)
    controls: (ControlOptions, dict)

    def __init__(self, camera_num=0, **opts_keywords):
        self.kw = opts_keywords
        self.transform = TransformOptions()
        self.main = StreamOptions(name="main")
        self.lores = StreamOptions(name="lores")
        self.raw = StreamOptions(name="raw")
        self.controls = ControlOptions(camera_num)
        if opts_keywords.keys() == list():
            pass
        for kwarg, val in opts_keywords.items():
            if isinstance(val, dict):
                if kwarg in ['main', 'lores', 'raw']:
                    setattr(self, kwarg, StreamOptions(kwarg, val))
                elif kwarg == 'transform':
                    setattr(self, kwarg, TransformOptions(val))
                elif kwarg == 'controls':
                    setattr(self, kwarg, ControlOptions(camera_num, val))
            elif (isinstance(val, StreamOptions) or isinstance(val, TransformOptions)):
                setattr(self, kwarg, val)
            elif isinstance(val, ControlOptions):
                setattr(self, kwarg, val)

    def fps(self, value):
        if isinstance(value, (int, float)):
            uS = int(1e6 / value)
            self.controls.FrameDurationLimits = (uS, uS)
        elif isinstance(value, (list, tuple)):
            uS_min, uS_max = int(1e6 / value[0]), int(1e6 / value[1])
            self.controls.FrameDurationLimits = (uS_min, uS_max)

    @property
    def config(self) -> dict:
        cfg = {'main': self.main.config,
               'lores': self.lores.config,
               'raw': self.raw.config,
               'transform': self.transform.config,
               'controls': self.controls.config}
        return cfg


def check_args(opts_args, opts_keywords):
    """Check to see if the user supplied non-keyword arguments or
    keyword arguments. For the classes that use this function, if using non-
    keyword arguments, the user must supply a dictionary. The other option is to
    supply keyword arguments. A mixture of both cannot be supplied."""
    if len(opts_args) == 1 and isinstance((opts_args[-1]), dict):
        opts = opts_args[-1]  # If the user supplied a dict.
    elif len(opts_args) > 1:
        raise SyntaxError("Supplied arguments must be a dict.")
    elif opts_keywords.keys() != list():
        opts = opts_keywords  # If the user supplied keywords...
    else:
        return False
    return opts
