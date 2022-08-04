#!/usr/bin/python3
"""picamera2 main class"""


import json
import os
import selectors
import tempfile
import threading
from enum import Enum
from typing import List
import time
from concurrent.futures import Future
from functools import partial

import libcamera
import numpy as np
from PIL import Image

from picamera2.encoders import Encoder, Quality, H264Encoder, MJPEGEncoder
from picamera2.outputs import FileOutput, FfmpegOutput
from picamera2.previews import DrmPreview, NullPreview, QtGlPreview, QtPreview
from picamera2.utils import initialize_logger

from .configuration import CameraConfiguration, StreamConfiguration
from .controls import Controls
from .request import CompletedRequest, Helpers
from .sensor_format import SensorFormat

STILL = libcamera.StreamRole.StillCapture
RAW = libcamera.StreamRole.Raw
VIDEO = libcamera.StreamRole.VideoRecording
VIEWFINDER = libcamera.StreamRole.Viewfinder


class Preview(Enum):
    """Enum that applications can pass to the start_preview method."""

    NULL = 0
    DRM = 1
    QT = 2
    QTGL = 3


class Picamera2:
    """Welcome to the PiCamera2 class."""

    @staticmethod
    def load_tuning_file(tuning_file, dir=None):
        """Load the named tuning file.

        If dir is given, then only that directory is checked,
        otherwise a list of likely installation directories is searched

        :param tuning_file: Tuning file
        :type tuning_file: str
        :param dir: Directory of tuning file, defaults to None
        :type dir: str, optional
        :raises RuntimeError: Produced if tuning file not found
        :return: Dictionary of tuning file
        :rtype: dict
        """
        if dir is not None:
            dirs = [dir]
        else:
            dirs = ["/home/pi/libcamera/src/ipa/raspberrypi/data",
                    "/usr/local/share/libcamera/ipa/raspberrypi",
                    "/usr/share/libcamera/ipa/raspberrypi"]
        for dir in dirs:
            file = os.path.join(dir, tuning_file)
            if os.path.isfile(file):
                with open(file, 'r') as fp:
                    return json.load(fp)
        raise RuntimeError("Tuning file not found")

    @staticmethod
    def find_tuning_algo(tuning: dict, name: str) -> dict:
        """
        Return the parameters for the named algorithm in the given camera tuning.

        :param tuning: The camera tuning object
        :type tuning: dict
        :param name: The name of the algorithm
        :type name: str
        :rtype: dict
        """
        version = tuning.get("version", 1)
        if version == 1:
            return tuning[name]
        return next(algo for algo in tuning["algorithms"] if name in algo)[name]

    def __init__(self, camera_num=0, verbose_console=None, tuning=None):
        """Initialise camera system and open the camera for use.

        :param camera_num: Camera index, defaults to 0
        :type camera_num: int, optional
        :param verbose_console: Logging level, defaults to None
        :type verbose_console: int, optional
        :param tuning: Tuning filename, defaults to None
        :type tuning: str, optional
        :raises RuntimeError: Init didn't complete
        """
        tuning_file = None
        if tuning is not None:
            if isinstance(tuning, str):
                os.environ["LIBCAMERA_RPI_TUNING_FILE"] = tuning
            else:
                tuning_file = tempfile.NamedTemporaryFile('w')
                json.dump(tuning, tuning_file)
                tuning_file.flush()  # but leave it open as closing it will delete it
                os.environ["LIBCAMERA_RPI_TUNING_FILE"] = tuning_file.name
        else:
            os.environ.pop("LIBCAMERA_RPI_TUNING_FILE", None)  # Use default tuning
        self.camera_manager = libcamera.CameraManager.singleton()
        self.camera_idx = camera_num
        if verbose_console is None:
            verbose_console = int(os.environ.get('PICAMERA2_LOG_LEVEL', '0'))
        self.verbose_console = verbose_console
        self.log = initialize_logger(console_level=verbose_console)
        self._reset_flags()
        self.helpers = Helpers(self)
        try:
            self._open_camera()
            self.log.debug(f"{self.camera_manager}")
            self.preview_configuration = self.create_preview_configuration()
            self.still_configuration = self.create_still_configuration()
            self.video_configuration = self.create_video_configuration()
        except Exception:
            self.log.error("Camera __init__ sequence did not complete.")
            raise RuntimeError("Camera __init__ sequence did not complete.")
        finally:
            if tuning_file is not None:
                tuning_file.close()  # delete the temporary file

    def _reset_flags(self) -> None:
        self.camera = None
        self.is_open = False
        self.camera_ctrl_info = {}
        self._preview = None
        self.camera_config = None
        self.libcamera_config = None
        self.streams = None
        self.stream_map = None
        self.started = False
        self.stop_count = 0
        self.configure_count = 0
        self.frames = 0
        self.functions = []
        self._future = None
        self.options = {}
        self._encoder = None
        self.pre_callback = None
        self.post_callback = None
        self.completed_requests = []
        self.lock = threading.Lock()  # protects the functions and completed_requests fields
        self.have_event_loop = False
        self.camera_properties_ = {}
        self.controls = Controls(self)
        self.sensor_modes_ = None

    @property
    def preview_configuration(self):
        return self.preview_configuration_

    @preview_configuration.setter
    def preview_configuration(self, value):
        self.preview_configuration_ = CameraConfiguration(value, self)

    @property
    def still_configuration(self):
        return self.still_configuration_

    @still_configuration.setter
    def still_configuration(self, value):
        self.still_configuration_ = CameraConfiguration(value, self)

    @property
    def video_configuration(self):
        return self.video_configuration_

    @video_configuration.setter
    def video_configuration(self, value):
        self.video_configuration_ = CameraConfiguration(value, self)

    @property
    def request_callback(self):
        """Now Deprecated"""
        self.log.error("request_callback is deprecated, returning post_callback instead")
        return self.post_callback

    @request_callback.setter
    def request_callback(self, value):
        """Now Deprecated"""
        self.log.error("request_callback is deprecated, setting post_callback instead")
        self.post_callback = value

    @property
    def asynchronous(self) -> bool:
        """True if there is threaded operation

        :return: Thread operation state
        :rtype: bool
        """
        return self._preview is not None and \
            getattr(self._preview, "thread", None) is not None and \
            self._preview.thread.is_alive()

    @property
    def camera_properties(self) -> dict:
        """Camera properties

        :return: Camera properties
        :rtype: dict
        """
        return {} if self.camera is None else self.camera_properties_

    @property
    def camera_controls(self) -> dict:
        return {k: (v[1].min, v[1].max, v[1].default) for k, v in self.camera_ctrl_info.items()}

    def __enter__(self):
        """Used for allowing use with context manager

        :return: self
        :rtype: Picamera2
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_traceback):
        """Used for allowing use with context manager

        :param exc_type: Exception type
        :type exc_type: Type[BaseException]
        :param exc_val: Exception
        :type exc_val: BaseException
        :param exc_traceback: Traceback
        :type exc_traceback: TracebackType
        """
        self.close()

    def __del__(self):
        """Without this libcamera will complain if we shut down without closing the camera."""
        self.log.debug(f"Resources now free: {self}")
        self.close()

    @staticmethod
    def _convert_from_libcamera_type(value):
        if isinstance(value, libcamera.Rectangle):
            value = (value.x, value.y, value.width, value.height)
        elif isinstance(value, libcamera.Size):
            value = (value.width, value.height)
        return value

    def _initialize_camera(self) -> bool:
        """Initialize camera

        :raises RuntimeError: Failure to initialise camera
        :return: True if success
        :rtype: bool
        """
        if self.camera_manager.cameras:
            if isinstance(self.camera_idx, str):
                try:
                    self.camera = self.camera_manager.get(self.camera_idx)
                except Exception:
                    self.camera = self.camera_manager.find(self.camera_idx)
            elif isinstance(self.camera_idx, int):
                self.camera = self.camera_manager.cameras[self.camera_idx]
        else:
            self.log.error("Camera(s) not found (Do not forget to disable legacy camera with raspi-config).")
            raise RuntimeError("Camera(s) not found (Do not forget to disable legacy camera with raspi-config).")

        if self.camera is not None:
            self.__identify_camera()

            # Re-generate the controls list to someting easer to use.
            for k, v in self.camera.controls.items():
                self.camera_ctrl_info[k.name] = (k, v)

            # Re-generate the properties list to someting easer to use.
            for k, v in self.camera.properties.items():
                self.camera_properties_[k.name] = self._convert_from_libcamera_type(v)

            # The next two lines could be placed elsewhere?
            self.sensor_resolution = self.camera_properties_["PixelArraySize"]
            self.sensor_format = str(self.camera.generate_configuration([RAW]).at(0).pixel_format)

            self.log.info('Initialization successful.')
            return True
        else:
            self.log.error("Initialization failed.")
            raise RuntimeError("Initialization failed.")

    def __identify_camera(self):
        for idx, address in enumerate(self.camera_manager.cameras):
            if address == self.camera:
                self.camera_idx = idx
                break

    def _open_camera(self) -> None:
        """Tries to open camera

        :raises RuntimeError: Failed to setup camera
        """
        if self._initialize_camera():
            if self.camera.acquire() >= 0:
                self.is_open = True
                self.log.info("Camera now open.")
            else:
                raise RuntimeError("Failed to acquire camera")
        else:
            raise RuntimeError("Failed to initialize camera")

    @property
    def sensor_modes(self) -> list:
        """The available sensor modes

        When called for the first time this will reconfigure the camera
        in order to read the modes.
        """
        if self.sensor_modes_ is not None:
            return self.sensor_modes_

        raw_config = self.camera.generate_configuration([libcamera.StreamRole.Raw])
        raw_formats = raw_config.at(0).formats
        self.sensor_modes_ = []

        for pix in raw_formats.pixel_formats:
            fmt = SensorFormat(str(pix))
            all_format = {}
            all_format["format"] = fmt
            all_format["unpacked"] = fmt.unpacked
            all_format["bit_depth"] = fmt.bit_depth
            for size in raw_formats.sizes(pix):
                cam_mode = all_format.copy()
                cam_mode["size"] = (size.width, size.height)
                temp_config = self.create_preview_configuration(raw={"format": str(pix), "size": cam_mode["size"]})
                self.configure(temp_config)
                frameDurationLimits = [i for i in self.camera_controls["FrameDurationLimits"] if i != 0]
                cam_mode["fps"] = round(1e6 / min(frameDurationLimits), 2)
                cam_mode["crop_limits"] = self.camera_properties["ScalerCropMaximum"]
                cam_mode["exposure_limits"] = tuple([i for i in self.camera_controls["ExposureTime"] if i != 0])
                self.sensor_modes_.append(cam_mode)
        return self.sensor_modes_

    def start_preview(self, preview=False, **kwargs) -> None:
        """
        Start the given preview which drives the camera processing.

        The preview may be either:
          None or False - in which case a NullPreview is made,
          True - which we hope in future to use to autodetect
          a Preview enum value - in which case a preview of that type is made,
          or an actual preview object.

        When using the enum form, extra keyword arguments can be supplied that
        will be forwarded to the preview class constructor.
        """
        if self.have_event_loop:
            raise RuntimeError("An event loop is already running")

        if preview is True:
            # Crude attempt at "autodetection" but which will mostly (?) work. We will
            # probably find situations that need fixing, VNC perhaps.
            display = os.getenv('DISPLAY')
            if display is None:
                preview = Preview.DRM
            elif display.startswith(':'):
                preview = Preview.QTGL
            else:
                preview = Preview.QT
        if not preview:  # i.e. None or False
            preview = NullPreview()
        elif isinstance(preview, Preview):
            preview_table = {Preview.NULL: NullPreview,
                             Preview.DRM: DrmPreview,
                             Preview.QT: QtPreview,
                             Preview.QTGL: QtGlPreview}
            preview = preview_table[preview](**kwargs)
        else:
            # Assume it's already a preview object.
            pass

        preview.start(self)
        self._preview = preview
        self.have_event_loop = True

    def stop_preview(self) -> None:
        """Stop preview

        :raises RuntimeError: Unable to stop preview
        """
        if self._preview:
            try:
                self._preview.stop()
                self._preview = None
                self.have_event_loop = False
            except Exception:
                raise RuntimeError("Unable to stop preview.")
        else:
            raise RuntimeError("No preview specified.")

    def close(self) -> None:
        """Close camera

        :raises RuntimeError: Closing failed
        """
        if self._preview:
            self.stop_preview()
        if self.is_open:
            self.stop()
            if self.camera.release() < 0:
                raise RuntimeError("Failed to release camera")
            self.is_open = False
            self.camera_config = None
            self.libcamera_config = None
            self.streams = None
            self.stream_map = None
            self.log.info('Camera closed successfully.')

    @staticmethod
    def _make_initial_stream_config(stream_config: dict, updates: dict, ignore_list=[]) -> dict:
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
                raise ValueError(f"Bad key '{key}': valid stream configuration keys are {valid}")
        return stream_config

    @staticmethod
    def _add_display_and_encode(config, display, encode) -> None:
        if display is not None and config.get(display, None) is None:
            raise RuntimeError(f"Display stream {display} was not defined")
        if encode is not None and config.get(encode, None) is None:
            raise RuntimeError(f"Encode stream {encode} was not defined")
        config['display'] = display
        config['encode'] = encode

    _raw_stream_ignore_list = ["bit_depth", "crop_limits", "exposure_limits", "fps", "unpacked"]

    def create_preview_configuration(self, main={}, lores=None, raw=None, transform=libcamera.Transform(), colour_space=libcamera.ColorSpace.Jpeg(), buffer_count=4, controls={}, display="main", encode="main"):
        """Make a configuration suitable for camera preview."""
        if self.camera is None:
            raise RuntimeError("Camera not opened")
        main = self._make_initial_stream_config({"format": "XBGR8888", "size": (640, 480)}, main)
        self.align_stream(main, optimal=False)
        lores = self._make_initial_stream_config({"format": "YUV420", "size": main["size"]}, lores)
        if lores is not None:
            self.align_stream(lores, optimal=False)
        raw = self._make_initial_stream_config({"format": self.sensor_format, "size": main["size"]}, raw, self._raw_stream_ignore_list)
        # Let the framerate vary from 12fps to as fast as possible.
        controls = {"NoiseReductionMode": libcamera.controls.draft.NoiseReductionModeEnum.Minimal,
                    "FrameDurationLimits": (100, 83333)} | controls
        config = {"use_case": "preview",
                  "transform": transform,
                  "colour_space": colour_space,
                  "buffer_count": buffer_count,
                  "main": main,
                  "lores": lores,
                  "raw": raw,
                  "controls": controls}
        self._add_display_and_encode(config, display, encode)
        return config

    def create_still_configuration(self, main={}, lores=None, raw=None, transform=libcamera.Transform(), colour_space=libcamera.ColorSpace.Jpeg(), buffer_count=1, controls={}, display=None, encode=None) -> dict:
        """Make a configuration suitable for still image capture. Default to 2 buffers, as the Gl preview would need them."""
        if self.camera is None:
            raise RuntimeError("Camera not opened")
        main = self._make_initial_stream_config({"format": "BGR888", "size": self.sensor_resolution}, main)
        self.align_stream(main, optimal=False)
        lores = self._make_initial_stream_config({"format": "YUV420", "size": main["size"]}, lores)
        if lores is not None:
            self.align_stream(lores, optimal=False)
        raw = self._make_initial_stream_config({"format": self.sensor_format, "size": main["size"]}, raw)
        # Let the framerate span the entire possible range of the sensor.
        controls = {"NoiseReductionMode": libcamera.controls.draft.NoiseReductionModeEnum.HighQuality,
                    "FrameDurationLimits": (100, 1000000 * 1000)} | controls
        config = {"use_case": "still",
                  "transform": transform,
                  "colour_space": colour_space,
                  "buffer_count": buffer_count,
                  "main": main,
                  "lores": lores,
                  "raw": raw,
                  "controls": controls}
        self._add_display_and_encode(config, display, encode)
        return config

    def create_video_configuration(self, main={}, lores=None, raw=None, transform=libcamera.Transform(), colour_space=None, buffer_count=6, controls={}, display="main", encode="main") -> dict:
        """Make a configuration suitable for video recording."""
        if self.camera is None:
            raise RuntimeError("Camera not opened")
        main = self._make_initial_stream_config({"format": "XBGR8888", "size": (1280, 720)}, main)
        self.align_stream(main, optimal=False)
        lores = self._make_initial_stream_config({"format": "YUV420", "size": main["size"]}, lores)
        if lores is not None:
            self.align_stream(lores, optimal=False)
        raw = self._make_initial_stream_config({"format": self.sensor_format, "size": main["size"]}, raw)
        if colour_space is None:
            # Choose default colour space according to the video resolution.
            if self.is_RGB(main["format"]):
                # There's a bug down in some driver where it won't accept anything other than
                # sRGB or JPEG as the colour space for an RGB stream. So until that is fixed:
                colour_space = libcamera.ColorSpace.Jpeg()
            elif main["size"][0] < 1280 or main["size"][1] < 720:
                colour_space = libcamera.ColorSpace.Smpte170m()
            else:
                colour_space = libcamera.ColorSpace.Rec709()
        controls = {"NoiseReductionMode": libcamera.controls.draft.NoiseReductionModeEnum.Fast,
                    "FrameDurationLimits": (33333, 33333)} | controls
        config = {"use_case": "video",
                  "transform": transform,
                  "colour_space": colour_space,
                  "buffer_count": buffer_count,
                  "main": main,
                  "lores": lores,
                  "raw": raw,
                  "controls": controls}
        self._add_display_and_encode(config, display, encode)
        return config

    def check_stream_config(self, stream_config, name) -> None:
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
            if not self.is_raw(format):
                raise RuntimeError("Unrecognised raw format " + format)
        else:
            if not self.is_YUV(format) and not self.is_RGB(format):
                raise RuntimeError("Bad format " + format + " in stream " + name)
        size = stream_config["size"]
        if type(size) is not tuple or len(size) != 2:
            raise RuntimeError("size in " + name + " stream should be (width, height)")
        if size[0] % 2 or size[1] % 2:
            raise RuntimeError("width and height should be even")

    def check_camera_config(self, camera_config: dict) -> None:
        required_keys = ["colour_space", "transform", "main", "lores", "raw"]
        for name in required_keys:
            if name not in camera_config:
                raise RuntimeError(f"'{name}' key expected in camera configuration")

        # Check the entire camera configuration for errors.
        if not isinstance(camera_config["colour_space"], libcamera._libcamera.ColorSpace):
            raise RuntimeError("Colour space has incorrect type")
        if not isinstance(camera_config["transform"], libcamera._libcamera.Transform):
            raise RuntimeError("Transform has incorrect type")

        self.check_stream_config(camera_config["main"], "main")
        if camera_config["lores"] is not None:
            self.check_stream_config(camera_config["lores"], "lores")
            main_w, main_h = camera_config["main"]["size"]
            lores_w, lores_h = camera_config["lores"]["size"]
            if lores_w > main_w or lores_h > main_h:
                raise RuntimeError("lores stream dimensions may not exceed main stream")
            if not self.is_YUV(camera_config["lores"]["format"]):
                raise RuntimeError("lores stream must be YUV")
        if camera_config["raw"] is not None:
            self.check_stream_config(camera_config["raw"], "raw")

    @staticmethod
    def _update_libcamera_stream_config(libcamera_stream_config, stream_config, buffer_count) -> None:
        # Update the libcamera stream config with ours.
        libcamera_stream_config.size = libcamera.Size(stream_config["size"][0], stream_config["size"][1])
        libcamera_stream_config.pixel_format = libcamera.PixelFormat(stream_config["format"])
        libcamera_stream_config.buffer_count = buffer_count

    def _make_libcamera_config(self, camera_config):
        # Make a libcamera configuration object from our Python configuration.

        # We will create each stream with the "viewfinder" role just to get the stream
        # configuration objects, and note the positions our named streams will have in
        # libcamera's stream list.
        roles = [VIEWFINDER]
        index = 1
        self.main_index = 0
        self.lores_index = -1
        self.raw_index = -1
        if camera_config["lores"] is not None:
            self.lores_index = index
            index += 1
            roles += [VIEWFINDER]
        if camera_config["raw"] is not None:
            self.raw_index = index
            roles += [RAW]

        # Make the libcamera configuration, and then we'll write all our parameters over
        # the ones it gave us.
        libcamera_config = self.camera.generate_configuration(roles)
        libcamera_config.transform = camera_config["transform"]
        buffer_count = camera_config["buffer_count"]
        self._update_libcamera_stream_config(libcamera_config.at(self.main_index), camera_config["main"], buffer_count)
        libcamera_config.at(self.main_index).color_space = camera_config["colour_space"]
        if self.lores_index >= 0:
            self._update_libcamera_stream_config(libcamera_config.at(self.lores_index), camera_config["lores"], buffer_count)
            libcamera_config.at(self.lores_index).color_space = camera_config["colour_space"]
        if self.raw_index >= 0:
            self._update_libcamera_stream_config(libcamera_config.at(self.raw_index), camera_config["raw"], buffer_count)
            libcamera_config.at(self.raw_index).color_space = libcamera.ColorSpace.Raw()

        return libcamera_config

    @staticmethod
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

    @staticmethod
    def align_configuration(config: dict, optimal=True) -> None:
        Picamera2.align_stream(config["main"], optimal=optimal)
        if "lores" in config and config["lores"] is not None:
            Picamera2.align_stream(config["lores"], optimal=optimal)
        # No point aligning the raw stream, it wouldn't mean anything.

    @staticmethod
    def is_YUV(fmt) -> bool:
        return fmt in ("NV21", "NV12", "YUV420", "YVU420", "YVYU", "YUYV", "UYVY", "VYUY")

    @staticmethod
    def is_RGB(fmt) -> bool:
        return fmt in ("BGR888", "RGB888", "XBGR8888", "XRGB8888")

    @staticmethod
    def is_Bayer(fmt) -> bool:
        return fmt in ("SBGGR8", "SGBRG8", "SGRBG8", "SRGGB8",
                       "SBGGR10", "SGBRG10", "SGRBG10", "SRGGB10",
                       "SBGGR10_CSI2P", "SGBRG10_CSI2P", "SGRBG10_CSI2P", "SRGGB10_CSI2P",
                       "SBGGR12", "SGBRG12", "SGRBG12", "SRGGB12",
                       "SBGGR12_CSI2P", "SGBRG12_CSI2P", "SGRBG12_CSI2P", "SRGGB12_CSI2P")

    @staticmethod
    def is_mono(fmt) -> bool:
        return fmt in ("R8", "R10", "R12", "R8_CSI2P", "R10_CSI2P", "R12_CSI2P")

    @staticmethod
    def is_raw(fmt) -> bool:
        return Picamera2.is_Bayer(fmt) or Picamera2.is_mono(fmt)

    def _make_requests(self) -> List[libcamera.Request]:
        """Make libcamera request objects.

        Makes as many as the number of buffers in the stream with the smallest number of buffers.

        :raises RuntimeError: Failure
        :return: requests
        :rtype: List[libcamera.Request]
        """
        num_requests = min([len(self.allocator.buffers(stream)) for stream in self.streams])
        requests = []
        for i in range(num_requests):
            request = self.camera.create_request()
            if request is None:
                raise RuntimeError("Could not create request")

            for stream in self.streams:
                if request.add_buffer(stream, self.allocator.buffers(stream)[i]) < 0:
                    raise RuntimeError("Failed to set request buffer")

            requests.append(request)

        return requests

    def _update_stream_config(self, stream_config, libcamera_stream_config) -> None:
        # Update our stream config from libcamera's.
        stream_config["format"] = str(libcamera_stream_config.pixel_format)
        stream_config["size"] = (libcamera_stream_config.size.width, libcamera_stream_config.size.height)
        stream_config["stride"] = libcamera_stream_config.stride
        stream_config["framesize"] = libcamera_stream_config.frame_size

    def _update_camera_config(self, camera_config, libcamera_config) -> None:
        """Update our camera config from libcamera's.

        :param camera_config: Camera configuration
        :type camera_config: dict
        :param libcamera_config: libcamera configuration
        :type libcamera_config: dict
        """
        camera_config["transform"] = libcamera_config.transform
        camera_config["colour_space"] = libcamera_config.at(0).color_space
        self._update_stream_config(camera_config["main"], libcamera_config.at(0))
        if self.lores_index >= 0:
            self._update_stream_config(camera_config["lores"], libcamera_config.at(self.lores_index))
        if self.raw_index >= 0:
            self._update_stream_config(camera_config["raw"], libcamera_config.at(self.raw_index))

    def configure_(self, camera_config="preview") -> None:
        """Configure the camera system with the given configuration.

        :param camera_config: Configuration, defaults to the 'preview' configuration
        :type camera_config: dict, string or CameraConfiguration, optional
        :raises RuntimeError: Failed to configure
        """
        if self.started:
            raise RuntimeError("Camera must be stopped before configuring")
        initial_config = camera_config
        if isinstance(initial_config, str):
            if initial_config == "preview":
                camera_config = self.preview_configuration
            elif initial_config == "still":
                camera_config = self.still_configuration
            else:
                camera_config = self.video_configuration
        if isinstance(camera_config, CameraConfiguration):
            if camera_config.raw is not None and camera_config.raw.format is None:
                camera_config.raw.format = self.sensor_format
            # We expect values to have been set for any lores/raw streams.
            camera_config = camera_config.make_dict()
        if camera_config is None:
            camera_config = self.create_preview_configuration()

        # Mark ourselves as unconfigured.
        self.libcamera_config = None
        self.camera_config = None

        # Check the config and turn it into a libcamera config.
        self.check_camera_config(camera_config)
        libcamera_config = self._make_libcamera_config(camera_config)

        # Check that libcamera is happy with it.
        status = libcamera_config.validate()
        self._update_camera_config(camera_config, libcamera_config)
        self.log.debug(f"Requesting configuration: {camera_config}")
        if status == libcamera.CameraConfiguration.Status.Invalid:
            raise RuntimeError("Invalid camera configuration: {}".format(camera_config))
        elif status == libcamera.CameraConfiguration.Status.Adjusted:
            self.log.info("Camera configuration has been adjusted!")

        # Configure libcamera.
        if self.camera.configure(libcamera_config):
            raise RuntimeError("Configuration failed: {}".format(camera_config))
        self.log.info("Configuration successful!")
        self.log.debug(f"Final configuration: {camera_config}")

        # Update the controls and properties list as some of the values may have changed.
        self.camera_ctrl_info = {}
        self.camera_properties_ = {}
        for k, v in self.camera.controls.items():
            self.camera_ctrl_info[k.name] = (k, v)
        for k, v in self.camera.properties.items():
            self.camera_properties_[k.name] = self._convert_from_libcamera_type(v)

        # Record which libcamera stream goes with which of our names.
        self.stream_map = {"main": libcamera_config.at(0).stream}
        self.stream_map["lores"] = libcamera_config.at(self.lores_index).stream if self.lores_index >= 0 else None
        self.stream_map["raw"] = libcamera_config.at(self.raw_index).stream if self.raw_index >= 0 else None
        self.log.debug(f"Streams: {self.stream_map}")

        # These name the streams that we will display/encode.
        self.display_stream_name = camera_config['display']
        if self.display_stream_name is not None and self.display_stream_name not in camera_config:
            raise RuntimeError(f"Display stream {self.display_stream_name} was not defined")
        self.encode_stream_name = camera_config['encode']
        if self.encode_stream_name is not None and self.encode_stream_name not in camera_config:
            raise RuntimeError(f"Encode stream {self.encode_stream_name} was not defined")
        elif self.encode_stream_name is None:
            # If no encode stream then remove the encoder
            self._encoder = None

        # Allocate all the frame buffers.
        self.streams = [stream_config.stream for stream_config in libcamera_config]
        self.allocator = libcamera.FrameBufferAllocator(self.camera)
        for i, stream in enumerate(self.streams):
            if self.allocator.allocate(stream) < 0:
                self.log.critical("Failed to allocate buffers.")
                raise RuntimeError("Failed to allocate buffers.")
            msg = f"Allocated {len(self.allocator.buffers(stream))} buffers for stream {i}."
            self.log.debug(msg)

        # Mark ourselves as configured.
        self.libcamera_config = libcamera_config
        self.camera_config = camera_config
        # Fill in the embedded configuration structures if those were used.
        if initial_config == "preview":
            self.preview_configuration.update(camera_config)
        elif initial_config == "still":
            self.still_configuration.update(camera_config)
        else:
            self.video_configuration.update(camera_config)
        # Set the controls directly so as to overwrite whatever is there.
        self.controls.set_controls(self.camera_config['controls'])
        self.configure_count += 1

    def configure(self, camera_config="preview") -> None:
        """Configure the camera system with the given configuration."""
        self.configure_(camera_config)

    def camera_configuration(self) -> dict:
        """Return the camera configuration."""
        return self.camera_config

    def stream_configuration(self, name="main") -> dict:
        """Return the stream configuration for the named stream."""
        return self.camera_config[name]

    def start_(self) -> None:
        """Start the camera system running."""
        if self.camera_config is None:
            raise RuntimeError("Camera has not been configured")
        if self.started:
            raise RuntimeError("Camera already started")
        controls = self.controls.get_libcamera_controls()
        if self.camera.start(controls) >= 0:
            for request in self._make_requests():
                self.camera.queue_request(request)
            self.log.info("Camera started")
            self.started = True
        else:
            self.log.error("Camera did not start properly.")
            raise RuntimeError("Camera did not start properly.")

    def start(self, config=None, show_preview=False) -> None:
        """
        Start the camera system running.

        Camera controls may be sent to the camera before it starts running.

        The following parameters may be supplied:

        config - if not None this is used to configure the camera. This is just a
            convenience so that you don't have to call configure explicitly.

        show_preview - whether to show a preview window. You can pass in the preview
            type or True to attempt to autodetect. If left as False you'll get no
            visible preview window but the "NULL preview" will still be run. The
            value None would mean no event loop runs at all and you would have to
            implement your own.
        """
        if self.camera_config is None and config is None:
            config = "preview"
        if config is not None:
            self.configure(config)
        if self.camera_config is None:
            raise RuntimeError("Camera has not been configured")
        # By default we will create an event loop is there isn't one running already.
        if show_preview is not None and not self.have_event_loop:
            self.start_preview(show_preview)
        self.start_()

    def stop_(self, request=None) -> None:
        """Stop the camera.

        Only call this function directly from within the camera event
        loop, such as in a Qt application.
        """
        if self.started:
            self.stop_count += 1
            self.camera.stop()

            # Temporary hack to flush Requests from the event queue.
            # This is needed to prevent old completed Requests from showing
            # up when the camera is started the next time.
            sel = selectors.DefaultSelector()
            sel.register(self.camera_manager.event_fd, selectors.EVENT_READ)
            events = sel.select(0)
            if events:
                self.camera_manager.get_ready_requests()

            self.started = False
            self.completed_requests = []
            self.log.info("Camera stopped")
        return (True, None)

    def stop(self) -> None:
        """Stop the camera."""
        if not self.started:
            self.log.debug("Camera was not started")
            return
        if self.asynchronous:
            self.dispatch_functions([self.stop_])
            self.wait()
        else:
            self.stop_()

    def set_controls(self, controls) -> None:
        """Set camera controls. These will be delivered with the next request that gets submitted."""
        self.controls.set_controls(controls)

    def _get_completed_requests(self) -> List[CompletedRequest]:
        # Return all the requests that libcamera has completed.
        requests = [CompletedRequest(req, self) for req in self.camera_manager.get_ready_requests()
                    if req.status == libcamera.Request.Status.Complete]
        self.frames += len(requests)
        return requests

    def process_requests(self) -> None:
        # This is the function that the event loop, which runs externally to us, must
        # call.
        requests = self._get_completed_requests()
        if not requests:
            return

        # It works like this:
        # * We maintain a list of the requests that libcamera has completed (completed_requests).
        #   But we keep only a minimal number here so that we have one available to "return
        #   quickly" if an application asks for it, but the rest get recycled to libcamera to
        #   keep the camera system running.
        # * The lock here protects the completed_requests list (because if it's non-empty, an
        #   application can pop a request from it asynchronously), and the functions list. If
        #   we don't have a request immediately available, the application will queue some
        #   "functions" for us to execute here in order to accomplish what it wanted.

        with self.lock:
            # These new requests all have one "use" recorded, which is the one for
            # being in this list.
            self.completed_requests += requests

            # This is the request we'll hand back to be displayed. This counts as a "use" too.
            display_request = self.completed_requests[-1]
            display_request.acquire()

            # Some applications may (for example) want us to draw something onto these images before
            # encoding or copying them for an application.
            if display_request and self.pre_callback:
                self.pre_callback(display_request)

            # See if any actions have been queued up for us to do here.
            # Each operation is regarded as completed when it returns True, otherwise it remains
            # in the list to be tried again next time.
            if self.functions:
                function = self.functions[0]
                self.log.debug(f"Execute function: {function}")
                try:
                    done, result = function()
                    if done:
                        self.functions = self.functions[1:]
                        # Once we've done everything, signal the fact to the thread that requested this work.
                        if not self.functions:
                            self._future.set_result(result)
                except Exception as e:
                    self.functions = []
                    self._future.set_exception(e)

            # Some applications may want to do something to the image after they've had a change
            # to copy it, but before it goes to the video encoder.
            if display_request and self.post_callback:
                self.post_callback(display_request)

            if self._encoder is not None:
                stream = self.stream_map[self.encode_stream_name]
                self._encoder.encode(stream, display_request)

            # We can only hang on to a limited number of requests here, most should be recycled
            # immediately back to libcamera. You could consider customising this number.
            # When there's only one buffer in total, don't hang on to anything as it would stall
            # the pipeline completely.
            max_len = 0 if self.camera_config['buffer_count'] == 1 else 1
            while len(self.completed_requests) > max_len:
                self.completed_requests.pop(0).release()

        # If one of the functions we ran reconfigured the camera since this request came out,
        # then we don't want it going back to the application as the memory is not valid.
        if display_request.configure_count != self.configure_count:
            display_request.release()
            display_request = None

        return display_request

    def wait(self):
        """Wait for the event loop to finish an operation and signal us."""
        result = self._future.result()
        self._future = None
        return result

    def _dispatch_functions(self, functions, signal_function=None) -> None:
        if self._future:
            raise RuntimeError("Failure to wait for previous operation to finish!")
        self._future = Future()
        self._future.set_running_or_notify_cancel()
        if signal_function is not None:
            self._future.add_done_callback(signal_function)
        self.functions = functions

    def dispatch_functions(self, functions, signal_function=None) -> None:
        """The main thread should use this to dispatch a number of operations for the event
        loop to perform.

        When there are multiple items each will be processed on a separate
        trip round the event loop, meaning that a single operation could stop and restart the
        camera and the next operation would receive a request from after the restart.
        """
        with self.lock:
            self._dispatch_functions(functions, signal_function)

    def capture_file_(self, file_output, name, format=None):
        request = self.completed_requests.pop(0)
        if name == "raw" and self.is_raw(self.camera_config["raw"]["format"]):
            request.save_dng(file_output)
        else:
            request.save(name, file_output, format=format)

        result = request.get_metadata()
        request.release()
        return (True, result)

    def _execute_or_dispatch(self, function, wait, signal_function):
        if wait is None:
            wait = signal_function is None
        with self.lock:
            if self._future:
                raise RuntimeError("Failure to wait for previous operation to finish!")
            self._dispatch_functions([function], signal_function)
            if self.completed_requests:
                done, result = function()
                if done:
                    self.functions = []
                    self._future.set_result(result)
        if wait:
            return self.wait()

    def capture_file(self, file_output, name="main", format=None, wait=None, signal_function=None):
        """Capture an image to a file in the current camera mode."""
        return self._execute_or_dispatch(partial(self.capture_file_, file_output, name, format=format),
                                         wait, signal_function)

    def switch_mode_(self, camera_config):
        self.stop_()
        self.configure_(camera_config)
        self.start_()
        return (True, self.camera_config)

    def switch_mode(self, camera_config, wait=None, signal_function=None):
        """Switch the camera into another mode given by the camera_config."""
        if wait is None:
            wait = signal_function is None
        functions = [partial(self.switch_mode_, camera_config)]
        self.dispatch_functions(functions, signal_function)
        if wait:
            return self.wait()

    def switch_mode_and_capture_file(self, camera_config, file_output, name="main", format=None, wait=None, signal_function=None):
        """Switch the camera into a new (capture) mode, capture an image to file, then return
        back to the initial camera mode.
        """
        if wait is None:
            wait = signal_function is None
        preview_config = self.camera_config

        def capture_and_switch_back_(self, file_output, preview_config, format):
            _, result = self.capture_file_(file_output, name, format=format)
            self.switch_mode_(preview_config)
            return (True, result)

        functions = [partial(self.switch_mode_, camera_config),
                     partial(capture_and_switch_back_, self, file_output, preview_config, format)]
        self.dispatch_functions(functions, signal_function)
        if wait:
            return self.wait()

    def capture_request_(self):
        # The "use" of this request is transferred from the completed_requests list to the caller.
        return (True, self.completed_requests.pop(0))

    def capture_request(self, wait=None, signal_function=None):
        """Fetch the next completed request from the camera system. You will be holding a
        reference to this request so you must release it again to return it to the camera system.
        """
        function = self.capture_request_
        return self._execute_or_dispatch(function, wait, signal_function)

    def switch_mode_capture_request_and_stop(self, camera_config, wait=None, signal_function=None):
        """Switch the camera into a new (capture) mode, capture a request in the new mode and then stop the camera."""
        if wait is None:
            wait = signal_function is None

        def capture_request_and_stop_(self):
            _, result = self.capture_request_()
            self.stop_()
            return (True, result)

        functions = [partial(self.switch_mode_, camera_config),
                     partial(capture_request_and_stop_, self)]
        self.dispatch_functions(functions, signal_function)
        if wait:
            return self.wait()

    def capture_metadata_(self):
        request = self.completed_requests.pop(0)
        result = request.get_metadata()
        request.release()
        return (True, result)

    def capture_metadata(self, wait=None, signal_function=None):
        """Fetch the metadata from the next camera frame."""
        function = self.capture_metadata_
        return self._execute_or_dispatch(function, wait, signal_function)

    def capture_buffer_(self, name):
        request = self.completed_requests.pop(0)
        result = request.make_buffer(name)
        request.release()
        return (True, result)

    def capture_buffer(self, name="main", wait=None, signal_function=None):
        """Make a 1d numpy array from the next frame in the named stream."""
        return self._execute_or_dispatch(partial(self.capture_buffer_, name), wait, signal_function)

    def capture_buffers_and_metadata_(self, names):
        request = self.completed_requests.pop(0)
        result = ([request.make_buffer(name) for name in names], request.get_metadata())
        request.release()
        return (True, result)

    def capture_buffers(self, names=["main"], wait=None, signal_function=None):
        """Make a 1d numpy array from the next frame for each of the named streams."""
        return self._execute_or_dispatch(partial(self.capture_buffers_and_metadata_, names), wait, signal_function)

    def switch_mode_and_capture_buffer(self, camera_config, name="main", wait=None, signal_function=None):
        """Switch the camera into a new (capture) mode, capture the first buffer, then return
        back to the initial camera mode.
        """
        if wait is None:
            wait = signal_function is None
        preview_config = self.camera_config

        def capture_buffer_and_switch_back_(self, preview_config, name):
            _, result = self.capture_buffer_(name)
            self.switch_mode_(preview_config)
            return (True, result)

        functions = [partial(self.switch_mode_, camera_config),
                     partial(capture_buffer_and_switch_back_, self, preview_config, name)]
        self.dispatch_functions(functions, signal_function)
        if wait:
            return self.wait()

    def switch_mode_and_capture_buffers(self, camera_config, names=["main"], wait=None, signal_function=None):
        """Switch the camera into a new (capture) mode, capture the first buffers, then return
        back to the initial camera mode.
        """
        if wait is None:
            wait = signal_function is None
        preview_config = self.camera_config

        def capture_buffers_and_switch_back_(self, preview_config, names):
            _, result = self.capture_buffers_and_metadata_(names)
            self.switch_mode_(preview_config)
            return (True, result)

        functions = [partial(self.switch_mode_, camera_config),
                     partial(capture_buffers_and_switch_back_, self, preview_config, names)]
        self.dispatch_functions(functions, signal_function)
        if wait:
            return self.wait()

    def capture_array_(self, name):
        request = self.completed_requests.pop(0)
        result = request.make_array(name)
        request.release()
        return (True, result)

    def capture_array(self, name="main", wait=None, signal_function=None):
        """Make a 2d image from the next frame in the named stream."""
        return self._execute_or_dispatch(partial(self.capture_array_, name), wait, signal_function)

    def capture_arrays_and_metadata_(self, names):
        request = self.completed_requests.pop(0)
        result = ([request.make_array(name) for name in names], request.get_metadata())
        request.release()
        return (True, result)

    def capture_arrays(self, names=["main"], wait=None, signal_function=None):
        """Make 2d image arrays from the next frames in the named streams."""
        return self._execute_or_dispatch(partial(self.capture_arrays_and_metadata_, names), wait, signal_function)

    def switch_mode_and_capture_array(self, camera_config, name="main", wait=None, signal_function=None):
        """Switch the camera into a new (capture) mode, capture the image array data, then return
        back to the initial camera mode."""
        if wait is None:
            wait = signal_function is None
        preview_config = self.camera_config

        def capture_array_and_switch_back_(self, preview_config, name):
            _, result = self.capture_array_(name)
            self.switch_mode_(preview_config)
            return (True, result)

        functions = [partial(self.switch_mode_, camera_config),
                     partial(capture_array_and_switch_back_, self, preview_config, name)]
        self.dispatch_functions(functions, signal_function)
        if wait:
            return self.wait()

    def switch_mode_and_capture_arrays(self, camera_config, names=["main"], wait=None, signal_function=None):
        """Switch the camera into a new (capture) mode, capture the image arrays, then return
        back to the initial camera mode."""
        if wait is None:
            wait = signal_function is None
        preview_config = self.camera_config

        def capture_arrays_and_switch_back_(self, preview_config, names):
            _, result = self.capture_arrays_and_metadata_(names)
            self.switch_mode_(preview_config)
            return (True, result)

        functions = [partial(self.switch_mode_, camera_config),
                     partial(capture_arrays_and_switch_back_, self, preview_config, names)]
        self.dispatch_functions(functions, signal_function)
        if wait:
            return self.wait()

    def capture_image_(self, name):
        """Capture image

        :param name: Stream name
        :type name: str
        """
        request = self.completed_requests.pop(0)
        result = request.make_image(name)
        request.release()
        return (True, result)

    def capture_image(self, name="main", wait=None, signal_function=None) -> Image:
        """Make a PIL image from the next frame in the named stream.

        :param name: Stream name, defaults to "main"
        :type name: str, optional
        :param wait: Wait for the event loop to finish an operation and signal us, defaults to True
        :type wait: bool, optional
        :param signal_function: Callback, defaults to None
        :type signal_function: function, optional
        :return: PIL Image
        :rtype: Image
        """
        return self._execute_or_dispatch(partial(self.capture_image_, name), wait, signal_function)

    def switch_mode_and_capture_image(self, camera_config, name="main", wait=None, signal_function=None):
        """Switch the camera into a new (capture) mode, capture the image, then return
        back to the initial camera mode.
        """
        if wait is None:
            wait = signal_function is None
        preview_config = self.camera_config

        def capture_image_and_switch_back_(self, preview_config, name):
            _, result = self.capture_image_(name)
            self.switch_mode_(preview_config)
            return (True, result)

        functions = [partial(self.switch_mode_, camera_config),
                     partial(capture_image_and_switch_back_, self, preview_config, name)]
        self.dispatch_functions(functions, signal_function)
        if wait:
            return self.wait()

    def start_encoder(self, encoder=None, quality=Quality.MEDIUM) -> None:
        """Start encoder

        :param encoder: Sets encoder or uses existing, defaults to None
        :type encoder: Encoder, optional
        :raises RuntimeError: No encoder set or no stream
        """
        if encoder is not None:
            self.encoder = encoder
        streams = self.camera_configuration()
        if self.encoder is None:
            raise RuntimeError("No encoder specified")
        name = self.encode_stream_name
        if streams.get(name, None) is None:
            raise RuntimeError(f"Encode stream {name} was not defined")
        self.encoder.width, self.encoder.height = streams[name]['size']
        self.encoder.format = streams[name]['format']
        self.encoder.stride = streams[name]['stride']
        # Also give the encoder a nominal framerate, which we'll peg at 30fps max
        # in case we only have a dummy value
        min_frame_duration = self.camera_ctrl_info["FrameDurationLimits"][1].min
        min_frame_duration = max(min_frame_duration, 33333)
        self.encoder.framerate = 1000000 / min_frame_duration
        # Finally the encoder must set up any remaining unknown parameters (e.g. bitrate).
        self.encoder._setup(quality)
        self.encoder._start()

    def stop_encoder(self) -> None:
        """Stops the encoder
        """
        self.encoder._stop()

    @property
    def encoder(self):
        """Extract current Encoder object

        :return: Encoder
        :rtype: Encoder
        """
        return self._encoder

    @encoder.setter
    def encoder(self, value):
        """Set Encoder to be used

        :param value: Encoder to be set
        :type value: Encoder
        :raises RuntimeError: Fail to pass Encoder
        """
        if not isinstance(value, Encoder):
            raise RuntimeError("Must pass encoder instance")
        self._encoder = value

    def start_recording(self, encoder, output, pts=None, config=None, quality=Quality.MEDIUM) -> None:
        """Start recording a video using the given encoder and to the given output.

        Output may be a string in which case the correspondingly named file is opened.

        :param encoder: Video encoder
        :type encoder: Encoder
        :param output: FileOutput object
        :type output: FileOutput
        """
        if self.camera_config is None and config is None:
            config = "video"
        if config is not None:
            self.configure(config)
        if isinstance(output, str):
            output = FileOutput(output, pts=pts)
        encoder.output = output
        self.start_encoder(encoder, quality)
        self.start()

    def stop_recording(self) -> None:
        """Stop recording a video. The encode and output are stopped and closed."""
        self.stop()
        self.stop_encoder()

    def set_overlay(self, overlay) -> None:
        """Display an overlay on the camera image.

        The overlay may be either None, in which case any overlay is removed,
        or a 4-channel ``ndarray``, the last of thechannels being taken as the alpha channel.

        :param overlay: Overlay or None
        :type overlay: ndarray
        :raises RuntimeError: Must pass a 4-channel image
        """
        if overlay is not None:
            if overlay.ndim != 3 or overlay.shape[2] != 4:
                raise RuntimeError("Overlay must be a 4-channel image")
        self._preview.set_overlay(overlay)

    def start_and_capture_files(self, name="image{:03d}.jpg", initial_delay=1, preview_mode="preview", capture_mode="still", num_files=1, delay=1, show_preview=True):
        """
        This function makes capturing multiple images more conenient, but should only be used in
        command line line applications (not from a Qt application, for example). If will configure
        the camera as requested and start it, switching between preview and still modes for
        capture. It supports the following parameters (all optional):

        name - name of the files to which to save the images. If more than one image is to be
            captured then it should feature a format directive that will be replaced by a counter.

        initial_delay - any time delay (in seconds) before the first image is captured. The camera
            will run in preview mode during this period. The default time is 1s.

        preview_mode - the camera mode to use for the preview phase (defaulting to the
            Picamera2 object's preview_configuration field).

        capture_mode - the camera mode to use to capture the still images (defaulting to the
            Picamera2 object's still_configuration field).

        num_files - number of files to capture (default 1).

        delay - the time delay for every capture after the first (default 1s).

        show_preview - whether to show a preview window (default: yes). The preview window only
            displays an image by default during the preview phase, so if captures are back-to-back
            with delay zero, then there may be no images shown. This parameter only has any
            effect if a preview is not already running. If it is, it would have to be stopped first
            (with the stop_preview method).
        """
        if self.started:
            self.stop()
        if delay:
            # Show a preview between captures, so we will switch mode and back for each capture.
            self.configure(preview_mode)
            self.start(show_preview=show_preview)
            for i in range(num_files):
                time.sleep(initial_delay if i == 0 else delay)
                self.switch_mode_and_capture_file(capture_mode, name.format(i))
        else:
            # No preview between captures, it's more efficient just to stay in capture mode.
            if initial_delay:
                self.configure(preview_mode)
                self.start(show_preview=show_preview)
                time.sleep(initial_delay)
                self.switch_mode(capture_mode)
            else:
                self.configure(capture_mode)
                self.start(show_preview=show_preview)
            for i in range(num_files):
                self.capture_file(name.format(i))
                if i == num_files - 1:
                    break
                time.sleep(delay)
        self.stop()

    def start_and_capture_file(self, name="image.jpg", delay=1, preview_mode="preview", capture_mode="still", show_preview=True):
        """
        This function makes capturing a single image more conenient, but should only be used in
        command line line applications (not from a Qt application, for example). If will configure
        the camera as requested and start it, switching from the preview to the still mode for
        capture. It supports the following parameters (all optional):

        name - name of the file to which to save the images.

        delay - any time delay (in seconds) before the image is captured. The camera
            will run in preview mode during this period. The default time is 1s.

        preview_mode - the camera mode to use for the preview phase (defaulting to the
            Picamera2 object's preview_configuration field).

        capture_mode - the camera mode to use to capture the still images (defaulting to the
            Picamera2 object's still_configuration field).

        show_preview - whether to show a preview window (default: yes). The preview window only
            displays an image by default during the preview phase. This parameter only has any
            effect if a preview is not already running. If it is, it would have to be stopped first
            (with the stop_preview method).
        """
        self.start_and_capture_files(name=name, initial_delay=delay, preview_mode=preview_mode, capture_mode=capture_mode, num_files=1, show_preview=show_preview)

    def start_and_record_video(self, output, encoder=None, config=None, quality=Quality.MEDIUM, show_preview=False, duration=0, audio=False):
        """
        This function makes video recording more convenient, but should only be used in command
        line applications (not from a Qt application, for example). It will configure the camera
        if requested and start it. The following parameters are required:

        output - the name of an output file (or an output object). If the output is a string,
            the correct output object will be created for "mp4" or "ts" files. All other formats
            will simply be written as flat files.

        The following parameters are optional:

        encoder - the encoder object to use. If unspecified, the MJPEGEncoder will be selected for
            files ending in ".mjpg" or .mjpeg", otherwise the H264Enccoder will be used.

        config - the camera configuration to apply. The default behaviour (given by the value None)
            is not to overwrite any existing configuration, though the "video" configuration will be
            applied if the camera is unconfigured.

        quality - an indication of the video quality to use. This will be ignored if the encoder
            object was created with all its quality parameters (such as bitrate) filled in.

        show_preview - whether to show a preview window (default: no). This parameter only has an
            effect if a preview is not already running, in which case that preview would need
            stopping first (using stop_preview) for any change to take effect.

        duration - the duration of the video. The function will wait this amount of time before
            stopping the recording and returning. The default behaviour is to return immediately
            and to leave the recoding running (the application will have to stop it later, for
            example by calling stop_recording).

        audio - whether to record audio. This is only effective when recording to an "mp4" or "ts"
            file, and there is a microphone installed and working as the default input device
            through Pulseaudio.
        """
        if self.started:
            self.stop()
        if self.camera_config is None and config is None:
            config = "video"
        if config is not None:
            self.configure(config)
        if isinstance(output, str):
            if encoder is None:
                extension = output.split('.')[-1].lower()
                if extension in ("mjpg", "mjpeg"):
                    encoder = MJPEGEncoder()
                if extension in ("mp4", "ts"):
                    output = FfmpegOutput(output, audio=audio)
                else:
                    output = FileOutput(output)
        if encoder is None:
            encoder = H264Encoder()
        encoder.output = output
        self.start_encoder(encoder, quality)
        self.start(show_preview=show_preview)
        if duration:
            time.sleep(duration)
            self.stop_recording()
