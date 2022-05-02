import libcamera


class Controls():
    """ A class for manipulating picamera2 controls.

    All instances of this class within the picamera2 module share the same
    values. Before the camera is started, whatever the user sets will
    take effect when the camera starts. Based on how the CompletedRequests
    class is structured, any reassignment of a control will take effect on
    the next request.

    Controls are type checked just before being passed to the
    camera manager. The user must supply the exact syntax for a control and
    its value as it is found in libcamera when creating the control.
    """

    AeConstraintMode: (int, str) = None
    AeEnable: (int, bool) = None
    AeExposureMode: (int, str) = None
    AeMeteringMode: (int, str) = None
    AePrecaptureTrigger: int = None
    AfTrigger: int = None
    AnalogueGain: (float, int) = None
    AwbEnable: (int, bool) = None
    AwbMode: (int, str) = None
    Brightness: (float, int) = None
    ColorCorrectionAberrationMode: (int, str) = None
    ColourCorrectionMatrix: (tuple, list) = None
    ColourGains: (tuple, list) = None
    Contrast: (float, int) = None
    DigitalGain: (float, int) = None
    ExposureTime: (float, int) = None
    ExposureValue: (float, int) = None
    FrameDurationLimits: (tuple, list) = None
    MaxLatency: int = None
    NoiseReductionMode: (int, str) = None
    PipelineDepth: int = None
    Saturation: (float, int) = None
    ScalerCrop: (tuple, list) = None
    SceneFlicker: (int, str) = None
    Sharpness: (float, int) = None
    TestPatternMode: (int, str) = None

    def __init__(self, controls_from_libcamera):
        self._camera_controls = dict(sorted(controls_from_libcamera.items()))
        self._current = {}
        self._fps = None

    @property
    def config(self) -> dict:
        """
        Get the user-defined controls configuration.
        This function is read-only. Any changes to the output of this
        function must either be issued as a property change
        (e.g. .Contrast = 1) or through the
        Picamera2().set_controls command as a supplied dictionary.

        The primary purpose is to deliver the user-defined controls to
        the camera start function. Users can also use it check to see what
        they defined the controls as BEFORE they start the camera.

        To check the controls after the camera has started, please use the
        current function.

        @return
            Returned is a dictionary of camera controls that the user wants to
            change. If all controls are set to none, then the returned dict
            is empty, which is still accepted by the camera_manager.
        """
        controls = {}
        for attr, types in self.__annotations__.items():
            val = getattr(self, attr)
            if (not isinstance(val, types) and
                    val is not None and
                    attr not in str(val)):
                raise TypeError(f"{attr} must be of these type(s): {types}")
            if isinstance(val, str):  # Assume val is mode if a string.
                val = getattr(getattr(libcamera, attr), val)
            controls[attr] = val
        user_defined = {k: v for k, v in controls.items() if v is not None}
        user_defined = dict(sorted(user_defined.items()))
        return user_defined

    @property
    def current(self) -> dict:
        """
        This function returns the current user-defined settings of the camera.
        It is only updated through the CompletedRequests module.
        """
        return self._current

    @property
    def _blank(self) -> None:
        """
        This function _blanks all controls to None.
        Its only use is to clear the controls at camera close. This is so
        that if a user decides to reopen the camera after close, the old
        control settings do not persist and carry over to the next start.
        """
        for attr in self.__annotations__.keys():
            setattr(self, attr, None)

    @property
    def fps(self) -> int:
        return self._fps

    @fps.setter
    def fps(self, value) -> None:
        """
        Converts a frames per seconds (fps) value to a microseconds value that
        the camera accepts.

        @param value
            A value with units of frames per second.
        @return
            A tuple of values indicated a microseconds value that enables
            a fixed number of frames per second.

        e.g. In: fps = 30
             Out: FrameDurationLimits = (33333,33333)
        """
        uS = int(1e6 / value)
        self.FrameDurationLimits = (uS, uS)

    @property
    def ranges(self) -> dict:
        """This function returns the possible ranges for each controls."""
        _ranges = {}
        for ctrl, val_tuple in self._camera_controls.items():
            _ranges[ctrl] = {'min': val_tuple[0], 'max': val_tuple[1]}
        _ranges = dict(sorted(_ranges.items()))
        return _ranges

    @property
    def defaults(self) -> dict:
        """This function takes the default camera controls and displays them
        as a dictionary to the user. In theory, this should update with changes
        to libcamera.camera.controls."""
        defaults = {}
        for ctrl, val_tuple in self._camera_controls.items():
            if ctrl == 'FrameDurationLimits':
                if not isinstance(ctrl, self.__annotations__[ctrl]):
                    default_v = [val_tuple[-1]] * 2
            elif ctrl == 'ColourCorrectionMatrix':
                if not isinstance(ctrl, self.__annotations__[ctrl]):
                    default_v = [val_tuple[-1]] * 9
            elif ctrl == 'ColourGains':
                if not isinstance(ctrl, self.__annotations__[ctrl]):
                    default_v = [val_tuple[-1]] * 2
            else:
                default_v = val_tuple[-1]
            defaults[ctrl] = default_v
        defaults = dict(sorted(defaults.items()))  # Sort it alphabetically.
        return defaults

    @property
    def reset(self) -> None:
        for ctrl, val in self.defaults.items():
            setattr(self, ctrl, val)