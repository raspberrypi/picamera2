import libcamera


class Controls():
    # It is probably bad form to specify a required type and then to set it as
    # NoneType, but the config functions searches for None and excludes them
    # when self.config is passed to the libcamera camera start function.
    # This doesn't break anything and the NoneTypes aren't viewable to the
    # user. I suppose NoneType could be added to the types tuple, but that may
    # lead to confusion for the end user by implying that setting a control to
    # None resets it to the original functionality, which is not the case.

    AeEnable: (int,bool) = None
    AeMeteringMode: (int,str) = None
    AeConstraintMode: (int,str) = None
    AeExposureMode: (int,str) = None
    ExposureValue: (float,int) = None
    ExposureTime: (float,int) = None
    AnalogueGain: (float,int) = None
    Brightness: (float,int) = None
    Contrast: (float,int) = None
    AwbEnable: (int,bool) = None
    AwbMode: (int,str) = None
    ColourGains: (tuple,list) = None
    Saturation: (float,int) = None
    Sharpness: (float,int) = None
    ColourCorrectionMatrix: (tuple,list) = None
    ScalerCrop: (tuple,list) = None
    DigitalGain: (float,int) = None
    FrameDurationLimits: (tuple,list) = None
    AePrecaptureTrigger: int = None
    AfTrigger: int = None
    NoiseReductionMode: (int,str) = None
    ColorCorrectionAberrationMode: (int,str) = None
    SceneFlicker: (int,str) = None
    PipelineDepth: int = None
    MaxLatency: int = None
    TestPatternMode: (int,str) = None

    def __init__(self,controls_from_libcamera):
        self._camera_controls = dict(sorted(controls_from_libcamera.items()))
        self._current = {}
        self._fps = None
        self.anno = self.__annotations__

    @property
    def config(self) -> dict:
        """
        Get the user-defined controls configuration.
        This function is read-only. Any changes to the output of this
        function must either be issued as a property change
        (e.g. .Contrast = 1) or through the
        Picamera2() set_controls command as a supplied dictionary.

        This function will use the __annotations__ attribute to obtain the
        class vars and their required types. It will also check to see if the
        class var is a libcamera._libcamera."control" type by simply converting
        the libcamera control value to a string and checking it against the
        name of the class var. Finally, for controls that have names for modes,
        the user can supply a string matching the exact syntax of the option.

        Finally, the function assumes that any control that is assigned a None
        doesn't need to be changed and excludes it from the return, ensuring
        that it is not passed to the camera_manager.

        @return
            Returned is a dictionary of camera controls that the user wants to
            change. If all controls are set to none, then the returned dict
            is empty, which is still accepted by the camera_manager.
        """
        controls = {}
        for attr, types in self.__annotations__.items():
            val = getattr(self,attr)
            if (not isinstance(val,types) #If not one of the defined types...
                    and val is not None  # or not defined as None...
                    and attr not in str(val)):  #or not a libcamera type...
                raise TypeError(f"{attr} must be of these type(s): {types}")
            if isinstance(val,str): #Assume val is mode if a string.
                val = getattr(getattr(libcamera,attr),val)
            controls[attr] = val
        user_defined = {k:v for k,v in controls.items() if v is not None}
        user_defined = dict(sorted(user_defined.items()))
        return user_defined

    @property
    def current(self):
        """
        This function returns the current user-defined settings of the camera.
        It is only updated through the CompletedRequests module.
        """
        current = dict(sorted(self._current.items()))
        return self._current

    @property
    def clear(self):
        """
        This function resets all controls to None.
        Its only use is to clear the controls at camera close.
        """
        for attr in self.__annotations__.keys():
            setattr(self,attr,None)

    @property
    def fps(self):
        return self._fps

    @fps.setter
    def fps(self,value) -> int:
        """
        Converts a frames per seconds value to a microseconds value that
        the camera accepts.
        @param value
            A value with units of frames per second.
        @return
            A tuple of values indicated a microseconds value that enables
            a fixed number of frames per second.
        """
        uS = int(1e6/value)
        self.FrameDurationLimits=(uS,uS)

    @property
    def ranges(self) -> dict:
        _ranges = {}
        for ctrl,val_tuple in self._camera_controls.items():
            _ranges[ctrl] = {'min': val_tuple[0],'max':val_tuple[1]}
        _ranges = dict(sorted(_ranges.items()))
        return _ranges

    @property
    def defaults(self) -> dict:
        defaults = {}
        for ctrl,val_tuple in self._camera_controls.items():
            if ctrl == 'FrameDurationLimits':
                if not isinstance(ctrl,self.__annotations__[ctrl]):
                    default_v = [val_tuple[-1]] * 2
            elif ctrl == 'ColourCorrectionMatrix':
                if not isinstance (ctrl,self.__annotations__[ctrl]):
                    default_v = [val_tuple[-1]] * 9
            elif ctrl == 'ColourGains':
                if not isinstance(ctrl,self.__annotations__[ctrl]):
                    default_v = [val_tuple[-1]] * 2
            else:
                default_v = val_tuple[-1]
            defaults[ctrl] = default_v
        defaults = dict(sorted(defaults.items())) #Sort it alphabetically.
        return defaults

    @property
    def reset(self):
        for k,v in self.defaults.items():
            setattr(self,k,v)

    #
    # @property
    # def doc(self):
    #     print(self.__doc__)

   #
   # """
   #  AeEnable:
   #      Set the enable or disable state of the auto exposure.
   #      Associated with ExposureTime and AnalogueGain.
   #      0 = disable
   #      1 = enable
   #  AeMeteringMode:
   #      Set the auto exposure metering mode. Modes determine which parts of the
   #      image dictate scene brightness. Some metering modes may be platform
   #      specific.
   #  AeConstraintMode:
   #      Set the auto exposure constraint mode. Modes determine how scene
   #      brightness is adjusted to reach the desired targe exposure. Some
   #      constraint modes may be platform specific.
   #  AeExposureMode:
   #      Set the auto exposure-exposure mode. Setting this mode specifies how the
   #      total exposure is divided between the shutter time and the analogue
   #      gain. Exposure mode may be platform specific.
   #  ExposureValue:
   #      Only applies when auto exposure is enabled.
   #      This parameter adjust the exposure as a function of log2.
   #      Associated with AeEnable.
   #  ExposureTime:
   #      Also considered the shutter speed for a frame. Value is specified
   #      in micro-seconds. Associated with AnalogueGain and AeEnable.
   #  AnalogueRain:
   #      Specifies the gain multiplier of all colour channels. Cannot be less
   #      than 1.0,with the exception of 0, which passes control back to auto
   #      exposure. Associated with ExposureTime and AeEnable.
   #  Brightness:
   #      Sets the brightness to a fixed value. Value can be between -1.0 (darker)
   #      and 1.0 (brighter). A value of 0 specifies no change.
   #  Contrast:
   #      Sets the contrast to a fixed value. Normal contrast has a value of 1.0.
   #      Anything greater will increase the contrast.
   #      Values smaller then 1.0 will decrease the contrast.
   #  AwbEnable:
   #      Enable or disable the auto white balance.
   #      Associated with ColourGains.
   #  AwbMode:
   #      Set a mode that adjusts the range of illuminants. Modes may be platform
   #      specific.
   #  ColourGains:
   #      Only works when AwbEnable is set to 0. Setting this value to a tuple or
   #      list of values changes the
   #      gain values for the red and blue channels, in that order.
   #  Saturation:
   #      Set a fixed saturation value. Normal is 1.0. Values greater than 1.0
   #      enhance saturation.
   #       A value of 0 produces a greyscale image.
   #  Sharpness:
   #      Adjust the sharpness of the image. 0 means no sharpness.
   #      Sharpening cannot be less than 0 and does not apply to raw streams.
   #  ColourCorrectionMatrix
   #      Settings that convert the camera RGB to sRGB.
   #  ScalerCrop
   #      Assigns dimensionality the portion of the image that is to be scaled.
   #  DigitalGain
   #      Applies to all colour channels of a raw image.
   #  FrameDurationLimits:
   #      The minimum and maximum frame duration allowed (in microseconds).
   #      Setting the minimum and maximum values to be the same creates a fixed
   #      frame duration.
   #      Example: [33333,33333]
   #          This is equivalent to setting the frame duration to a fixed 33,333
   #          microseconds. 1e6 uS/S * (1frame/33333uS) = 30 frames per second
   #  AePrecaptureTrigger:
   #      Controls the auto exposure metering trigger.
   #  AfTrigger:
   #      Controls when the auto focus is triggered.
   #  NoiseReductionMode:
   #      Select the noise reduction mode.
   #      0 = No noise reduction is applied.
   #      1 = Noise reduction applied with no impact to frame rate.
   #      2 = High quality noise reduction, but with lost of frame rate.
   #      3 = Minimal noise reduction with reduced impact to framerate.
   #      4 = Noise reduction is applied at different levels to different streams.
   #  ColorCorrectionAberrationMode:
   #      Controls what mode is used for chromatic aberration correction.
   #      0 = No correction.
   #      1 = Some correction with no impact to frame rate.
   #      2 = High quality correction with some potential impact to frame rate.
   #  MaxLatency:
   #      The number of frames that can occur after a request has been
   #      submitted before synchronisity between the camera and newest
   #      request is true.
   #      -1 = Unknown latency
   #      0 = Per-frame control
   #  TestPatternMode
   #      Select a test pattern control mode.
   #  """