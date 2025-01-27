#!/usr/bin/python3
"""picamera2 main class"""

import atexit
import contextlib
import json
import logging
import os
import selectors
import sys
import tempfile
import threading
import time
from enum import Enum
from functools import partial
from typing import Any, Dict, List, Tuple

import libcamera
import numpy as np
from libcamera import controls
from PIL import Image

import picamera2.formats as formats
import picamera2.platform as Platform
import picamera2.utils as utils
from picamera2.allocators import Allocator, DmaAllocator
from picamera2.encoders import Encoder, H264Encoder, MJPEGEncoder, Quality
from picamera2.outputs import FfmpegOutput, FileOutput
from picamera2.previews import DrmPreview, NullPreview, QtGlPreview, QtPreview

from .configuration import CameraConfiguration
from .controls import Controls
from .job import Job
from .request import CompletedRequest, Helpers
from .sensor_format import SensorFormat

STILL = libcamera.StreamRole.StillCapture
RAW = libcamera.StreamRole.Raw
VIDEO = libcamera.StreamRole.VideoRecording
VIEWFINDER = libcamera.StreamRole.Viewfinder

_log = logging.getLogger(__name__)


class Preview(Enum):
    """Enum that applications can pass to the start_preview method."""

    NULL = 0
    DRM = 1
    QT = 2
    QTGL = 3


class CameraManager:
    def __init__(self):
        self.running = False
        self.cameras = {}
        self._lock = threading.Lock()
        self._cms = None

    def setup(self):
        self.thread = threading.Thread(target=self.listen, daemon=True)
        self.running = True
        self.thread.start()

    @property
    def cms(self):
        if self._cms is None:
            self._cms = libcamera.CameraManager.singleton()
        return self._cms

    def reset(self):
        with self._lock:
            self._cms = None
            self._cms = libcamera.CameraManager.singleton()

    def add(self, index, camera):
        with self._lock:
            self.cameras[index] = camera
            if not self.running:
                self.setup()

    def cleanup(self, index):
        flag = False
        with self._lock:
            del self.cameras[index]
            if self.cameras == {}:
                self.running = False
                flag = True
        if flag:
            self.thread.join()
            self._cms = None

    def listen(self):
        sel = selectors.DefaultSelector()
        sel.register(self.cms.event_fd, selectors.EVENT_READ, self.handle_request)

        while self.running:
            events = sel.select(0.2)
            for key, _ in events:
                callback = key.data
                callback()

        sel.unregister(self.cms.event_fd)
        self._cms = None

    def handle_request(self, flushid=None):
        """Handle requests

        :param cameras: Dictionary of Picamera2
        :type cameras: dict
        """
        with self._lock:
            cams = set()
            for req in self.cms.get_ready_requests():
                if req.status == libcamera.Request.Status.Complete and req.cookie != flushid:
                    cams.add(req.cookie)
                    with self.cameras[req.cookie]._requestslock:
                        self.cameras[req.cookie]._requests += [CompletedRequest(req, self.cameras[req.cookie])]
            for c in cams:
                os.write(self.cameras[c].notifyme_w, b"\x00")


class Picamera2:
    """Welcome to the PiCamera2 class."""

    platform = Platform.get_platform()

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL
    _cm = CameraManager()

    @staticmethod
    def set_logging(level=logging.WARN, output=sys.stderr, msg=None):
        """Configure logging for simple standalone use cases.

        For example:
        Picamera2.set_logging(Picamera2.INFO)
        Picamera2.set_logging(level=Picamera2.DEBUG, msg="%(levelname)s: %(message)s")

        :param level: A logging level
        :type level: int
        :param output: An output stream for the messages
        :type output: file-like object
        :param msg: Logging message format
        :type msg: str
        """
        # Users of this method probably want everything to get logged.
        log = logging.getLogger("picamera2")
        log.handlers.clear()

        if level is not None:
            log.setLevel(level)

        if output is not None:
            handler = logging.StreamHandler(output)
            log.addHandler(handler)

            if msg is None:
                msg = "%(name)s %(levelname)s: %(message)s"
            handler.setFormatter(logging.Formatter(msg))

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
            platform_dir = "vc4" if Picamera2.platform == Platform.Platform.VC4 else "pisp"
            dirs = [os.path.expanduser("~/libcamera/src/ipa/rpi/" + platform_dir + "/data"),
                    "/usr/local/share/libcamera/ipa/rpi/" + platform_dir,
                    "/usr/share/libcamera/ipa/rpi/" + platform_dir]
        for directory in dirs:
            file = os.path.join(directory, tuning_file)
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

    @staticmethod
    def global_camera_info() -> list:
        """Return Id string and Model name for all attached cameras, one dict per camera.

        Ordered correctly by camera number. Also return the location and rotation
        of the camera when known, as these may help distinguish which is which.
        """
        def describe_camera(cam, num):
            info = {k.name: v for k, v in cam.properties.items() if k.name in ("Model", "Location", "Rotation")}
            info["Id"] = cam.id
            info["Num"] = num
            return info
        cameras = [describe_camera(cam, i) for i, cam in enumerate(Picamera2._cm.cms.cameras)]
        # Sort alphabetically so they are deterministic, but send USB cams to the back of the class.
        return sorted(cameras, key=lambda cam: ("/usb" not in cam['Id'], cam['Id']), reverse=True)

    def __init__(self, camera_num=0, verbose_console=None, tuning=None, allocator=None):
        """Initialise camera system and open the camera for use.

        :param camera_num: Camera index, defaults to 0
        :type camera_num: int, optional
        :param verbose_console: Unused
        :type verbose_console: int, optional
        :param tuning: Tuning filename, defaults to None
        :type tuning: str, optional
        :raises RuntimeError: Init didn't complete
        """
        if verbose_console is not None:
            _log.warning("verbose_console parameter is no longer used, use Picamera2.set_logging instead")
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
        self.notifyme_r, self.notifyme_w = os.pipe2(os.O_NONBLOCK)
        self.notifymeread = os.fdopen(self.notifyme_r, 'rb')
        # Set these before trying to open the camera in case that fails (shutting stuff down may check them).
        self._preview = None
        self.is_open = False
        # Get the real libcamera internal number.
        camera_num = self.global_camera_info()[camera_num]['Num']
        self._cm.add(camera_num, self)
        self.camera_idx = camera_num
        self.request_lock = threading.Lock()  # global lock used by requests
        self._requestslock = threading.Lock()
        self._requests = []
        if verbose_console is None:
            verbose_console = int(os.environ.get('PICAMERA2_LOG_LEVEL', '0'))
        self.verbose_console = verbose_console
        self._reset_flags()
        self.helpers = Helpers(self)
        try:
            self._open_camera()
            _log.debug(f"{self.camera_manager}")
            # We deliberately make raw streams with no size so that it will be filled in
            # later once the main stream size has been set.
            self.preview_configuration_ = CameraConfiguration(self.create_preview_configuration(), self)
            self.preview_configuration_.enable_raw()  # causes the size to be reset to None
            self.still_configuration_ = CameraConfiguration(self.create_still_configuration(), self)
            self.still_configuration_.enable_raw()  # ditto
            self.video_configuration_ = CameraConfiguration(self.create_video_configuration(), self)
            self.video_configuration_.enable_raw()  # ditto
        except Exception:
            _log.error("Camera __init__ sequence did not complete.")
            raise RuntimeError("Camera __init__ sequence did not complete.")
        finally:
            if tuning_file is not None:
                tuning_file.close()  # delete the temporary file
        # Quitting Python without stopping the camera sometimes causes crashes, with Boost logging
        # apparently being the principal culprit. Anyway, this seems to prevent the problem.
        atexit.register(self.close)
        # Set Allocator
        self.allocator = DmaAllocator() if allocator is None else allocator

    @property
    def camera_manager(self):
        return Picamera2._cm.cms

    def _reset_flags(self) -> None:
        self.camera = None
        self.camera_ctrl_info = {}
        self.camera_config = None
        self.libcamera_config = None
        self.streams = None
        self.stream_map = None
        self.started = False
        self.stop_count = 0
        self.configure_count = 0
        self.frames = 0
        self._job_list = []
        self.options = {}
        self._encoders = set()
        self.pre_callback = None
        self.post_callback = None
        self.completed_requests: List[CompletedRequest] = []
        self.lock = threading.Lock()  # protects the _job_list and completed_requests fields
        self._event_loop_running = False
        self._preview_stopped = threading.Event()
        self.camera_properties_ = {}
        self.controls = Controls(self)
        self.sensor_modes_ = None
        self._title_fields = None
        self._frame_drops = 0

    @property
    def preview_configuration(self) -> CameraConfiguration:
        return self.preview_configuration_

    @preview_configuration.setter
    def preview_configuration(self, value):
        self.preview_configuration_ = CameraConfiguration(value, self)

    @property
    def still_configuration(self) -> CameraConfiguration:
        return self.still_configuration_

    @still_configuration.setter
    def still_configuration(self, value):
        self.still_configuration_ = CameraConfiguration(value, self)

    @property
    def video_configuration(self) -> CameraConfiguration:
        return self.video_configuration_

    @video_configuration.setter
    def video_configuration(self, value):
        self.video_configuration_ = CameraConfiguration(value, self)

    @property
    def request_callback(self):
        """Now Deprecated"""
        _log.error("request_callback is deprecated, returning post_callback instead")
        return self.post_callback

    @request_callback.setter
    def request_callback(self, value):
        """Now Deprecated"""
        _log.error("request_callback is deprecated, setting post_callback instead")
        self.post_callback = value

    @property
    def camera_properties(self) -> dict:
        """Camera properties

        :return: Camera properties
        :rtype: dict
        """
        return {} if self.camera is None else self.camera_properties_

    @property
    def camera_controls(self) -> dict:
        return {k: (utils.convert_from_libcamera_type(v[1].min),
                    utils.convert_from_libcamera_type(v[1].max),
                    utils.convert_from_libcamera_type(v[1].default)) for k, v in self.camera_ctrl_info.items()}

    @property
    def title_fields(self):
        """The metadata fields reported in the title bar of any preview window."""
        return self._title_fields

    @title_fields.setter
    def title_fields(self, fields):
        def make_title(fields, metadata):
            def tidy(item):
                if isinstance(item, float):
                    return round(item, 3)
                elif isinstance(item, tuple):
                    return tuple(tidy(i) for i in item)
                else:
                    return item
            return "".join("{} {} ".format(f, tidy(metadata.get(f, "INVALID"))) for f in fields)  # noqa

        self._title_fields = fields
        function = None if fields is None else (lambda md: make_title(fields, md))
        if self._preview is not None:
            self._preview.set_title_function(function)

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
        _log.debug(f"Resources now free: {self}")
        self.close()

    def _grab_camera(self, idx):
        if isinstance(idx, str):
            try:
                return self.camera_manager.get(idx)
            except Exception:
                return self.camera_manager.find(idx)
        elif isinstance(idx, int):
            return self.camera_manager.cameras[idx]

    def _initialize_camera(self) -> None:
        """Initialize camera

        :raises RuntimeError: Failure to initialise camera
        """
        if not self.camera_manager.cameras:
            _log.error("Camera(s) not found (Do not forget to disable legacy camera with raspi-config).")
            raise RuntimeError("Camera(s) not found (Do not forget to disable legacy camera with raspi-config).")

        self.camera = self._grab_camera(self.camera_idx)

        if self.camera is None:
            _log.error("Initialization failed.")
            raise RuntimeError("Initialization failed.")

        self.__identify_camera()
        # Re-generate the controls list to someting easer to use.
        for k, v in self.camera.controls.items():
            self.camera_ctrl_info[k.name] = (k, v)

        # Re-generate the properties list to someting easer to use.
        for k, v in self.camera.properties.items():
            self.camera_properties_[k.name] = utils.convert_from_libcamera_type(v)

        # These next lines could be placed elsewhere?
        self._raw_modes = self._get_raw_modes()
        self._native_mode = self._select_native_mode(self._raw_modes)
        self.sensor_resolution = self._native_mode['size']
        self.sensor_format = self._native_mode['format']

        _log.info('Initialization successful.')

    def __identify_camera(self):
        for idx, address in enumerate(self.camera_manager.cameras):
            if address == self.camera:
                self.camera_idx = idx
                break

    def _open_camera(self) -> None:
        """Tries to open camera

        :raises RuntimeError: Failed to setup camera
        """
        try:
            self._initialize_camera()
        except RuntimeError:
            raise RuntimeError("Failed to initialize camera")

        # This now throws an error if it can't open the camera.
        self.camera.acquire()

        self.is_open = True
        _log.info("Camera now open.")

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
            name = str(pix)
            if not formats.is_raw(name):
                # Not a raw sensor so we can't deduce much about it. Quote the name and carry on.
                self.sensor_modes_.append({"format": name})
                continue
            fmt = SensorFormat(name)
            all_format = {}
            all_format["format"] = fmt
            all_format["unpacked"] = fmt.unpacked
            all_format["bit_depth"] = fmt.bit_depth
            for size in raw_formats.sizes(pix):
                cam_mode = all_format.copy()
                cam_mode["size"] = (size.width, size.height)
                temp_config = self.create_preview_configuration(raw={"format": str(pix), "size": cam_mode["size"]})
                self.configure(temp_config)
                frameDurationMin = self.camera_controls["FrameDurationLimits"][0]
                cam_mode["fps"] = round(1e6 / frameDurationMin, 2)
                _, scaler_crop_max, _ = self.camera_controls['ScalerCrop']
                cam_mode["crop_limits"] = scaler_crop_max
                cam_mode["exposure_limits"] = tuple([i for i in self.camera_controls["ExposureTime"] if i != 0])
                self.sensor_modes_.append(cam_mode)
        return self.sensor_modes_

    def _get_raw_modes(self) -> list:
        raw_config = self.camera.generate_configuration([libcamera.StreamRole.Raw])
        raw_formats = raw_config.at(0).formats
        raw_modes = []
        for pix in raw_formats.pixel_formats:
            fmt = str(pix)
            raw_modes += [{'format': fmt, 'size': (size.width, size.height)} for size in raw_formats.sizes(pix)]
        return raw_modes

    def _select_native_mode(self, modes):
        best_mode = modes[0]
        is_rpi_camera = self._is_rpi_camera()

        def area(sz):
            return sz[0] * sz[1]

        for mode in modes[1:]:
            if area(mode['size']) > area(best_mode['size']) or \
               (is_rpi_camera and area(mode['size']) == area(best_mode['size']) and
                   SensorFormat(mode['format']).bit_depth > SensorFormat(best_mode['format']).bit_depth):
                best_mode = mode
        return best_mode

    def attach_preview(self, preview) -> None:
        if self._preview:
            raise RuntimeError("Preview is already running")
        self._preview = preview
        self._event_loop_running = True

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
        if self._event_loop_running:
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

        # The preview windows call the attach_preview method.
        self._preview_stopped.clear()
        preview.start(self)

    def detach_preview(self) -> None:
        self._preview = None
        self._event_loop_running = False
        self._preview_stopped.set()

    def stop_preview(self) -> None:
        """Stop preview

        :raises RuntimeError: Unable to stop preview
        """
        if not self._preview:
            raise RuntimeError("No preview specified.")

        try:
            # The preview windows call the detach_preview method.
            self._preview.stop()
            self._preview_stopped.wait()
        except Exception:
            raise RuntimeError("Unable to stop preview.")

    def close(self) -> None:
        """Close camera

        :raises RuntimeError: Closing failed
        """
        atexit.unregister(self.close)
        if self._preview:
            self.stop_preview()
        if not self.is_open:
            return

        self.stop()
        # camera.release() now throws an error if it fails.
        self.camera.release()
        self._cm.cleanup(self.camera_idx)
        self.is_open = False
        self.streams = None
        self.stream_map = None
        self.camera = None
        self.camera_ctrl_info = {}
        self.camera_config = None
        self.libcamera_config = None
        self.preview_configuration = {}
        self.still_configuration = {}
        self.video_configuration = {}
        self.notifymeread.close()
        os.close(self.notifyme_w)
        # Clean up the allocator
        del self.allocator
        self.allocator = Allocator()
        _log.info('Camera closed successfully.')

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
        valid = ("format", "size", "stride", "preserve_ar")
        for key, value in updates.items():
            if isinstance(value, SensorFormat):
                value = str(value)
            if key in valid:
                stream_config[key] = value
            elif key in ignore_list:
                pass  # allows us to pass items from the sensor_modes as a raw stream
            else:
                raise ValueError(f"Bad key {key!r}: valid stream configuration keys are {valid}")
        return stream_config

    def _is_rpi_camera(self):
        """Is this camera handled by Raspberry Pi code or not (e.g. a USB cam)"""
        return 'ColorFilterArrangement' in self.camera_properties

    @staticmethod
    def _add_display_and_encode(config, display, encode) -> None:
        if display is not None and config.get(display, None) is None:
            raise RuntimeError(f"Display stream {display} was not defined")
        if encode is not None and config.get(encode, None) is None:
            raise RuntimeError(f"Encode stream {encode} was not defined")
        config['display'] = display
        config['encode'] = encode

    _raw_stream_ignore_list = ["bit_depth", "crop_limits", "exposure_limits", "fps", "unpacked"]

    def create_preview_configuration(self, main={}, lores=None, raw={}, transform=libcamera.Transform(),
                                     colour_space=libcamera.ColorSpace.Sycc(), buffer_count=4, controls={},
                                     display="main", encode="main", queue=True, sensor={}, use_case="preview") -> dict:
        """Make a configuration suitable for camera preview."""
        if self.camera is None:
            raise RuntimeError("Camera not opened")
        # USB cams can't deliver a raw stream.
        if not self._is_rpi_camera():
            raw = None
            sensor = None
        main = self._make_initial_stream_config({"format": "XBGR8888", "size": (640, 480), "preserve_ar": True}, main)
        self.align_stream(main, optimal=False)
        lores = self._make_initial_stream_config({"format": "YUV420", "size": main["size"], "preserve_ar": False}, lores)
        if lores is not None:
            self.align_stream(lores, optimal=False)
        raw = self._make_initial_stream_config({"format": self.sensor_format, "size": main["size"]},
                                               raw, self._raw_stream_ignore_list)
        # Let the framerate vary from 12fps to as fast as possible.
        if "NoiseReductionMode" in self.camera_controls and "FrameDurationLimits" in self.camera_controls:
            controls = {"NoiseReductionMode": libcamera.controls.draft.NoiseReductionModeEnum.Minimal,
                        "FrameDurationLimits": (100, 83333)} | controls
        config = {"use_case": use_case,
                  "transform": transform,
                  "colour_space": colour_space,
                  "buffer_count": buffer_count,
                  "queue": queue,
                  "main": main,
                  "lores": lores,
                  "raw": raw,
                  "controls": controls,
                  "sensor": sensor}
        self._add_display_and_encode(config, display, encode)
        return config

    def create_still_configuration(self, main={}, lores=None, raw={}, transform=libcamera.Transform(),
                                   colour_space=libcamera.ColorSpace.Sycc(), buffer_count=1, controls={},
                                   display=None, encode=None, queue=True, sensor={}, use_case="still") -> dict:
        """Make a configuration suitable for still image capture. Default to 2 buffers, as the Gl preview would need them."""
        if self.camera is None:
            raise RuntimeError("Camera not opened")
        # USB cams can't deliver a raw stream.
        if not self._is_rpi_camera():
            raw = None
            sensor = None
        main = self._make_initial_stream_config({"format": "BGR888", "size": self.sensor_resolution, "preserve_ar": True},
                                                main)
        self.align_stream(main, optimal=False)
        lores = self._make_initial_stream_config({"format": "YUV420", "size": main["size"], "preserve_ar": False}, lores)
        if lores is not None:
            self.align_stream(lores, optimal=False)
        raw = self._make_initial_stream_config({"format": self.sensor_format, "size": main["size"]},
                                               raw, self._raw_stream_ignore_list)
        # Let the framerate span the entire possible range of the sensor.
        if "NoiseReductionMode" in self.camera_controls and "FrameDurationLimits" in self.camera_controls:
            controls = {"NoiseReductionMode": libcamera.controls.draft.NoiseReductionModeEnum.HighQuality,
                        "FrameDurationLimits": (100, 1000000 * 1000)} | controls
        config = {"use_case": use_case,
                  "transform": transform,
                  "colour_space": colour_space,
                  "buffer_count": buffer_count,
                  "queue": queue,
                  "main": main,
                  "lores": lores,
                  "raw": raw,
                  "controls": controls,
                  "sensor": sensor}
        self._add_display_and_encode(config, display, encode)
        return config

    def create_video_configuration(self, main={}, lores=None, raw={}, transform=libcamera.Transform(),
                                   colour_space=None, buffer_count=6, controls={}, display="main",
                                   encode="main", queue=True, sensor={}, use_case="video") -> dict:
        """Make a configuration suitable for video recording."""
        if self.camera is None:
            raise RuntimeError("Camera not opened")
        # USB cams can't deliver a raw stream.
        if not self._is_rpi_camera():
            raw = None
            sensor = None
        main = self._make_initial_stream_config({"format": "XBGR8888", "size": (1280, 720), "preserve_ar": True}, main)
        self.align_stream(main, optimal=False)
        lores = self._make_initial_stream_config({"format": "YUV420", "size": main["size"], "preserve_ar": False}, lores)
        if lores is not None:
            self.align_stream(lores, optimal=False)
        raw = self._make_initial_stream_config({"format": self.sensor_format, "size": main["size"]},
                                               raw, self._raw_stream_ignore_list)
        if colour_space is None:
            # Choose default colour space according to the video resolution.
            if main["size"][0] < 1280 or main["size"][1] < 720:
                colour_space = libcamera.ColorSpace.Smpte170m()
            else:
                colour_space = libcamera.ColorSpace.Rec709()
        if "NoiseReductionMode" in self.camera_controls and "FrameDurationLimits" in self.camera_controls:
            controls = {"NoiseReductionMode": libcamera.controls.draft.NoiseReductionModeEnum.Fast,
                        "FrameDurationLimits": (33333, 33333)} | controls
        config = {"use_case": use_case,
                  "transform": transform,
                  "colour_space": colour_space,
                  "buffer_count": buffer_count,
                  "queue": queue,
                  "main": main,
                  "lores": lores,
                  "raw": raw,
                  "controls": controls,
                  "sensor": sensor}
        self._add_display_and_encode(config, display, encode)
        return config

    def check_stream_config(self, stream_config, name) -> None:
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
                raise RuntimeError("Unrecognised raw format " + format)
        else:
            # Allow "MJPEG" as we have some support for USB MJPEG-type cameras.
            if not formats.is_YUV(format) and not formats.is_RGB(format) and format != 'MJPEG':
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
                raise RuntimeError(f"{name!r} key expected in camera configuration")

        # Check the entire camera configuration for errors.
        if not isinstance(camera_config["colour_space"], libcamera._libcamera.ColorSpace):
            raise RuntimeError("Colour space has incorrect type")
        if not isinstance(camera_config["transform"], libcamera._libcamera.Transform):
            raise RuntimeError("Transform has incorrect type")

        if 'sensor' in camera_config and camera_config['sensor'] is not None:
            allowed_keys = {'bit_depth', 'output_size'}
            bad_keys = set(camera_config['sensor'].keys()).difference(allowed_keys)
            if bad_keys:
                raise RuntimeError(f"Unexpected keys {bad_keys} in sensor configuration")

        self.check_stream_config(camera_config["main"], "main")
        if camera_config["lores"] is not None:
            self.check_stream_config(camera_config["lores"], "lores")
            main_w, main_h = camera_config["main"]["size"]
            lores_w, lores_h = camera_config["lores"]["size"]
            if lores_w > main_w or lores_h > main_h:
                raise RuntimeError("lores stream dimensions may not exceed main stream")
            if Picamera2.platform == Platform.Platform.VC4 and not formats.is_YUV(camera_config["lores"]["format"]):
                raise RuntimeError("lores stream must be YUV")
        if camera_config["raw"] is not None:
            self.check_stream_config(camera_config["raw"], "raw")

    @staticmethod
    def _update_libcamera_stream_config(libcamera_stream_config, stream_config, buffer_count) -> None:
        # Update the libcamera stream config with ours.
        libcamera_stream_config.size = libcamera.Size(stream_config["size"][0], stream_config["size"][1])
        libcamera_stream_config.pixel_format = libcamera.PixelFormat(stream_config["format"])
        libcamera_stream_config.buffer_count = buffer_count
        # Stride is sometimes set to None in the stream_config, so need to guard against that case
        if stream_config.get("stride") is not None:
            libcamera_stream_config.stride = stream_config["stride"]
        else:
            libcamera_stream_config.stride = 0

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
        libcamera_config.orientation = utils.transform_to_orientation(camera_config["transform"])
        buffer_count = camera_config["buffer_count"]
        self._update_libcamera_stream_config(libcamera_config.at(self.main_index), camera_config["main"], buffer_count)
        libcamera_config.at(self.main_index).color_space = utils.colour_space_to_libcamera(
            camera_config["colour_space"],
            camera_config["main"]["format"])
        if self.lores_index >= 0:
            self._update_libcamera_stream_config(libcamera_config.at(self.lores_index), camera_config["lores"], buffer_count)
            # Must be YUV, so no need for colour_space_to_libcamera.
            libcamera_config.at(self.lores_index).color_space = camera_config["colour_space"]
        if self.raw_index >= 0:
            self._update_libcamera_stream_config(libcamera_config.at(self.raw_index), camera_config["raw"], buffer_count)
            libcamera_config.at(self.raw_index).color_space = libcamera.ColorSpace.Raw()

        if not self._is_rpi_camera():
            return libcamera_config

        # We're always going to set up the sensor config fully.
        bit_depth = 0
        if camera_config['sensor'] is not None and 'bit_depth' in camera_config['sensor'] and \
           camera_config['sensor']['bit_depth'] is not None:
            bit_depth = camera_config['sensor']['bit_depth']
        elif 'raw' in camera_config and camera_config['raw'] is not None and 'format' in camera_config['raw']:
            bit_depth = SensorFormat(camera_config['raw']['format']).bit_depth
        else:
            bit_depth = SensorFormat(self.sensor_format).bit_depth

        output_size = None
        if camera_config['sensor'] is not None and 'output_size' in camera_config['sensor'] and \
           camera_config['sensor']['output_size'] is not None:
            output_size = camera_config['sensor']['output_size']
        elif 'raw' in camera_config and camera_config['raw'] is not None and 'size' in camera_config['raw']:
            output_size = camera_config['raw']['size']
        else:
            output_size = camera_config['main']['size']

        # Now find a camera mode that best matches these, and that's what we use.
        # This function copies how libcamera scores modes:
        def score_mode(mode, bit_depth, output_size):
            mode_bit_depth = SensorFormat(mode['format']).bit_depth
            mode_output_size = mode['size']
            ar = output_size[0] / output_size[1]
            mode_ar = mode_output_size[0] / mode_output_size[1]

            def score_format(desired, actual):
                score = desired - actual
                return -score / 4 if score < 0 else score * 2

            score = score_format(output_size[0], mode_output_size[0])
            score += score_format(output_size[1], mode_output_size[1])
            score += 1500 * score_format(ar, mode_ar)
            score += 500 * abs(bit_depth - mode_bit_depth)
            return score

        mode = min(self._raw_modes, key=lambda x: score_mode(x, bit_depth, output_size))
        libcamera_config.sensor_config = libcamera.SensorConfiguration()
        libcamera_config.sensor_config.bit_depth = SensorFormat(mode['format']).bit_depth
        libcamera_config.sensor_config.output_size = libcamera.Size(*mode['size'])

        return libcamera_config

    @staticmethod
    def align_stream(stream_config: dict, optimal=True) -> None:
        if optimal:
            # Adjust the image size so that all planes are a mutliple of 32/64 bytes wide.
            # This matches the hardware behaviour and means we can be more efficient.
            align = 32 if Picamera2.platform == Platform.Platform.VC4 else 64
            if stream_config["format"] in ("YUV420", "YVU420"):
                align *= 2  # because the UV planes will have half this alignment
            elif stream_config["format"] in ("XBGR8888", "XRGB8888", "RGB161616", "BGR161616"):
                align //= 2  # we have an automatic extra factor of 2 here
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
            request = self.camera.create_request(self.camera_idx)
            if request is None:
                raise RuntimeError("Could not create request")

            for stream in self.streams:
                # This now throws an error if it fails.
                request.add_buffer(stream, self.allocator.buffers(stream)[i])
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
        camera_config["transform"] = utils.orientation_to_transform(libcamera_config.orientation)
        camera_config["colour_space"] = utils.colour_space_from_libcamera(libcamera_config.at(0).color_space)
        self._update_stream_config(camera_config["main"], libcamera_config.at(0))
        if self.lores_index >= 0:
            self._update_stream_config(camera_config["lores"], libcamera_config.at(self.lores_index))
        if self.raw_index >= 0:
            self._update_stream_config(camera_config["raw"], libcamera_config.at(self.raw_index))

        if libcamera_config.sensor_config is not None:
            sensor_config = {}
            sensor_config['bit_depth'] = libcamera_config.sensor_config.bit_depth
            sensor_config['output_size'] = utils.convert_from_libcamera_type(libcamera_config.sensor_config.output_size)
            camera_config['sensor'] = sensor_config

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
        elif isinstance(initial_config, dict):
            camera_config = camera_config.copy()
        if isinstance(camera_config, CameraConfiguration):
            if camera_config.raw is not None:
                # For raw streams, patch up the format/size now if they haven't been set.
                if camera_config.raw.format is None:
                    camera_config.raw.format = self.sensor_format
                if camera_config.raw.size is None:
                    camera_config.raw.size = camera_config.main.size
            # We expect values to have been set for any lores/raw streams.
            camera_config = camera_config.make_dict()
        if camera_config is None:
            camera_config = self.create_preview_configuration()
        # Be 100% sure that non-Pi cameras aren't asking for a raw stream.
        if not self._is_rpi_camera():
            camera_config['raw'] = None

        # Mark ourselves as unconfigured.
        self.libcamera_config = None
        self.camera_config = None

        # Check the config and turn it into a libcamera config.
        self.check_camera_config(camera_config)
        libcamera_config = self._make_libcamera_config(camera_config)
        self.libcamera_config = libcamera_config

        # Check that libcamera is happy with it.
        status = libcamera_config.validate()
        self._update_camera_config(camera_config, libcamera_config)
        _log.debug(f"Requesting configuration: {camera_config}")
        if status == libcamera.CameraConfiguration.Status.Invalid:
            raise RuntimeError(f"Invalid camera configuration: {camera_config}")
        elif status == libcamera.CameraConfiguration.Status.Adjusted:
            _log.info("Camera configuration has been adjusted!")

        # Configure libcamera.
        if self.camera.configure(libcamera_config):
            raise RuntimeError(f"Configuration failed: {camera_config}")
        _log.info("Configuration successful!")
        _log.debug(f"Final configuration: {camera_config}")

        # Update the controls and properties list as some of the values may have changed.
        self.camera_ctrl_info = {}
        self.camera_properties_ = {}
        for k, v in self.camera.controls.items():
            self.camera_ctrl_info[k.name] = (k, v)
        for k, v in self.camera.properties.items():
            self.camera_properties_[k.name] = utils.convert_from_libcamera_type(v)

        # Record which libcamera stream goes with which of our names.
        self.stream_map = {"main": libcamera_config.at(0).stream}
        self.stream_map["lores"] = libcamera_config.at(self.lores_index).stream if self.lores_index >= 0 else None
        self.stream_map["raw"] = libcamera_config.at(self.raw_index).stream if self.raw_index >= 0 else None
        _log.debug(f"Streams: {self.stream_map}")

        # These name the streams that we will display/encode.
        self.display_stream_name = camera_config['display']
        if self.display_stream_name is not None and self.display_stream_name not in camera_config:
            raise RuntimeError(f"Display stream {self.display_stream_name} was not defined")
        self.encode_stream_name = camera_config['encode']
        if self.encode_stream_name is not None and self.encode_stream_name not in camera_config:
            raise RuntimeError(f"Encode stream {self.encode_stream_name} was not defined")

        # Decide whether we are going to keep hold of the last completed request, or
        # whether capture requests will always wait for the next frame. If there's only
        # one buffer, never hang on to the request because it would stall the pipeline
        # instantly.
        if camera_config['queue'] and camera_config['buffer_count'] > 1:
            self._max_queue_len = 1
        else:
            self._max_queue_len = 0

        # Allocate all the frame buffers.
        self.streams = [stream_config.stream for stream_config in libcamera_config]
        self.allocator.allocate(libcamera_config, camera_config.get("use_case"))
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
        self.controls = Controls(self, controls=self.camera_config['controls'])
        self.configure_count += 1

        if "ScalerCrops" in self.camera_controls:
            par_crop = self.camera_controls["ScalerCrops"]
            full_fov = self.camera_controls["ScalerCrop"][1]
            scaler_crops = [par_crop[0] if camera_config["main"]["preserve_ar"] else full_fov]
            if self.lores_index >= 0:
                scaler_crops.append(par_crop[1] if camera_config["lores"]["preserve_ar"] else scaler_crops[0])
            self.set_controls({"ScalerCrops": scaler_crops})

    def configure(self, camera_config=None) -> None:
        """Configure the camera system with the given configuration. Defaults to the 'preview' configuration."""
        self.configure_("preview" if camera_config is None else camera_config)

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
            return
        controls = self.controls.get_libcamera_controls()
        self.controls = Controls(self)
        # camera.start() now throws an error if it fails.
        self.camera.start(controls)
        for request in self._make_requests():
            self.camera.queue_request(request)
        _log.info("Camera started")
        self.started = True

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
        if show_preview is not None and not self._event_loop_running:
            self.start_preview(show_preview)
        self.start_()

    def cancel_all_and_flush(self) -> None:
        """
        Clear the camera system queue of pending jobs and cancel them.

        Depending on what was happening at the time, this may leave the camera system in
        an indeterminate state. This function is really only intended for tidying up
        after an operation has unexpectedly timed out (for example, the camera cable has
        become dislodged) so that the camera can be closed.
        """
        with self.lock:
            for job in self._job_list:
                job.cancel()
            self._job_list = []

    def stop_(self, request=None) -> None:
        """Stop the camera.

        Only call this function directly from within the camera event
        loop, such as in a Qt application.
        """
        if self.started:
            self.stop_count += 1
            self.camera.stop()

            # Flush Requests from the event queue.
            # This is needed to prevent old completed Requests from showing
            # up when the camera is started the next time.
            self._cm.handle_request(self.camera_idx)
            self.started = False
            with self._requestslock:
                unseen_requests = self._requests
                self._requests = []
            for r in unseen_requests:
                r.release()
            while len(self.completed_requests) > 0:
                self.completed_requests.pop(0).release()
            self.completed_requests = []
            _log.info("Camera stopped")
        return (True, None)

    def stop(self) -> None:
        """Stop the camera."""
        if not self.started:
            _log.debug("Camera was not started")
            return
        # If the event loop is running in another thread, we need to send it a message
        # to stop, otherwise we can stop directly. When running a proper Qt app, _preview
        # is unset because we expect this code to be running the the Qt thread.
        if self._preview is not None and self._event_loop_running:
            self.dispatch_functions([self.stop_], wait=True, immediate=True)
        else:
            self.stop_()

    def set_controls(self, controls) -> None:
        """Set camera controls. These will be delivered with the next request that gets submitted."""
        self.controls.set_controls(controls)

    def process_requests(self, display) -> None:
        # This is the function that the event loop, which runs externally to us, must
        # call.
        requests = []
        with self._requestslock:
            requests = self._requests
            self._requests = []
        self.frames += len(requests)
        # It works like this:
        # * We maintain a list of the requests that libcamera has completed (completed_requests).
        #   But we keep only a minimal number here so that we have one available to "return
        #   quickly" if an application asks for it, but the rest get recycled to libcamera to
        #   keep the camera system running.
        # * The lock here protects the completed_requests list (because if it's non-empty, an
        #   application can pop a request from it asynchronously), and the _job_list. If
        #   we don't have a request immediately available, the application will queue a
        #   "job" for us to execute here in order to accomplish what it wanted.

        with self.lock:
            # These new requests all have one "use" recorded, which is the one for
            # being in this list.  Increase by one, so it cant't get discarded in
            # self.functions block.
            for req in requests:
                req.acquire()
            self.completed_requests += requests

            # This is the request we'll hand back to be displayed. This counts as a "use" too.
            display_request = None
            if requests:
                display_request = requests[-1]
                display_request.acquire()
                display_request.display = True  # display requests by default

            if self.pre_callback:
                for req in requests:
                    # Some applications may (for example) want us to draw something onto these images before
                    # encoding or copying them for an application.
                    self.pre_callback(req)

            # See if we have a job to do. When executed, if it returns True then it's done and
            # we can discard it. Otherwise it remains here to be tried again next time.
            finished_jobs = []
            while self._job_list:
                _log.debug(f"Execute job: {self._job_list[0]}")
                if self._job_list[0].execute():
                    finished_jobs.append(self._job_list.pop(0))
                else:
                    break

            for req in requests:
                # Some applications may want to do something to the image after they've had a change
                # to copy it, but before it goes to the video encoder.
                if self.post_callback:
                    self.post_callback(req)

                for encoder in self._encoders:
                    if encoder.name in self.stream_map:
                        encoder.encode(encoder.name, req)

                req.release()

            # We hang on to the last completed request if we have been asked to.
            while len(self.completed_requests) > self._max_queue_len:
                self.completed_requests.pop(0).release()

        # If one of the functions we ran reconfigured the camera since this request came out,
        # then we don't want it going back to the application as the memory is not valid.
        if display_request is not None:
            if display_request.configure_count == self.configure_count and \
               display_request.config['display'] is not None and display_request.display:
                display.render_request(display_request)
            display_request.release()

        for job in finished_jobs:
            job.signal()

    def _run_process_requests(self):
        """Cause the process_requests method to run in the event loop again."""
        os.write(self.notifyme_w, b"\x00")

    def wait(self, job, timeout=None):
        """Wait for the given job to finish (if necessary) and return its final result.

        The job is obtained either by calling one of the Picamera2 methods asynchronously
        (passing wait=False), or as a parameter to the signal_function that can be
        supplied to those same methods.
        """
        return job.get_result(timeout=timeout)

    def dispatch_functions(self, functions, wait, signal_function=None, immediate=False) -> None:
        """The main thread should use this to dispatch a number of operations for the event loop to perform.

        When there are multiple items each will be processed on a separate
        trip round the event loop, meaning that a single operation could stop and restart the
        camera and the next operation would receive a request from after the restart.

        The wait parameter should be one of:
            True - wait as long as necessary for the operation to compelte
            False - return immediately, giving the caller a "job" they can wait for
            None - default, if a signal_function was given do not wait, otherwise wait as long as necessary
            a number - wait for this number of seconds before raising a "timed out" error.
        """
        if wait is None:
            wait = signal_function is None
        timeout = wait
        if timeout is True:
            timeout = None
        with self.lock:
            only_job = not self._job_list
            job = Job(functions, signal_function)
            self._job_list.append(job)
            # If we're the only job now, and there are completed_requests queued up, then
            # it's worth prodding the event loop immediately as that request may be all we
            # need. We also prod the event loop if "immediate" is set, which can happen for
            # operations that begin by stopping the camera (such as mode switches, or simple
            # stop commands, for which no requests are needed).
            if only_job and (self.completed_requests or immediate):
                self._run_process_requests()
        return job.get_result(timeout=timeout) if wait else job

    def set_frame_drops_(self, num_frames):
        """Only for use within the camera event loop before calling drop_frames_."""  # noqa
        self._frame_drops = num_frames
        return (True, None)

    def drop_frames_(self):
        while self.completed_requests:
            if self._frame_drops == 0:
                return (True, None)
            self.completed_requests.pop(0).release()
            self._frame_drops -= 1
        return (False, None)

    def wait_for_timestamp_(self, timestamp_ns):
        # No wait requested. This function in the job is done.
        if not timestamp_ns:
            return (True, None)
        while self.completed_requests:
            # Check if frame started being exposed after the timestamp.
            md = self.completed_requests[0].get_metadata()
            frame_timestamp_ns = md['SensorTimestamp'] - 1000 * md['ExposureTime']
            if frame_timestamp_ns >= timestamp_ns:
                return (True, None)
            self.completed_requests.pop(0).release()
        return (False, None)

    def drop_frames(self, num_frames, wait=None, signal_function=None):
        """Drop num_frames frames from the camera."""
        functions = [partial(self.set_frame_drops_, num_frames), self.drop_frames_]
        return self.dispatch_functions(functions, wait, signal_function, immediate=True)

    def capture_file_(self, file_output, name: str, format=None, exif_data=None) -> dict:
        if not self.completed_requests:
            return (False, None)
        request = self.completed_requests.pop(0)
        if name == "raw" and formats.is_raw(self.camera_config["raw"]["format"]):
            request.save_dng(file_output)
        else:
            request.save(name, file_output, format=format, exif_data=exif_data)

        result = request.get_metadata()
        request.release()
        return (True, result)

    def capture_file(
            self,
            file_output,
            name: str = "main",
            format=None,
            wait=None,
            signal_function=None,
            exif_data=None) -> dict:
        """Capture an image to a file in the current camera mode.

        Return the metadata for the frame captured.

        exif_data - dictionary containing user defined exif data (based on `piexif`). This will
            overwrite existing exif information generated by picamera2.
        """
        functions = [partial(self.capture_file_, file_output, name, format=format,
                             exif_data=exif_data)]
        return self.dispatch_functions(functions, wait, signal_function)

    def switch_mode_(self, camera_config):
        self.stop_()
        self.configure_(camera_config)
        self.start_()
        return (True, self.camera_config)

    def switch_mode(self, camera_config, wait=None, signal_function=None):
        """Switch the camera into another mode given by the camera_config."""
        functions = [partial(self.switch_mode_, camera_config)]
        return self.dispatch_functions(functions, wait, signal_function, immediate=True)

    def switch_mode_and_drop_frames(self, camera_config, num_frames, wait=None, signal_function=None):
        """Switch the camera into the mode given by camera_config and drop the first num_frames frames."""
        functions = [partial(self.switch_mode_, camera_config),
                     partial(self.set_frame_drops_, num_frames), self.drop_frames_]
        return self.dispatch_functions(functions, wait, signal_function, immediate=True)

    def switch_mode_and_capture_file(self, camera_config, file_output, name="main", format=None,
                                     wait=None, signal_function=None, exif_data=None, delay=0):
        """Switch the camera into a new (capture) mode, capture an image to file.

        Then return back to the initial camera mode.

        exif_data - dictionary containing user defined exif data (based on `piexif`). This will
            overwrite existing exif information generated by picamera2.
        """
        preview_config = self.camera_config

        def capture_and_switch_back_(self, file_output, preview_config, format, exif_data=exif_data):
            done, result = self.capture_file_(file_output, name, format=format, exif_data=exif_data)
            if not done:
                return (False, None)
            self.switch_mode_(preview_config)
            return (True, result)

        functions = [partial(self.switch_mode_, camera_config),
                     partial(self.set_frame_drops_, delay), self.drop_frames_,
                     partial(capture_and_switch_back_, self, file_output, preview_config, format,
                             exif_data=exif_data)]
        return self.dispatch_functions(functions, wait, signal_function, immediate=True)

    def switch_mode_and_capture_request(self, camera_config, wait=None, signal_function=None, delay=0):
        """Switch the camera into a new (capture) mode and capture a request, then switch back.

        Applications should use this with care because it may increase the risk of CMA heap
        fragmentation. It may be preferable to use switch_mode_capture_request_and_stop and to
        release the request before restarting the original camera mode.
        """
        preview_config = self.camera_config

        def capture_and_switch_back_(self, preview_config):
            done, result = self.capture_request_()
            if not done:
                return (False, None)
            self.switch_mode_(preview_config)
            return (True, result)

        functions = [partial(self.switch_mode_, camera_config),
                     partial(self.set_frame_drops_, delay), self.drop_frames_,
                     partial(capture_and_switch_back_, self, preview_config)]
        return self.dispatch_functions(functions, wait, signal_function, immediate=True)

    def capture_request_(self):
        # The "use" of this request is transferred from the completed_requests list to the caller.
        if not self.completed_requests:
            return (False, None)
        return (True, self.completed_requests.pop(0))

    def capture_request(self, wait=None, signal_function=None, flush=None):
        """Fetch the next completed request from the camera system.

        You will be holding a reference to this request so you must release it again to return it
        to the camera system.
        """
        # flush will be the timestamp in ns that we wait for (if any)
        if flush is True:
            flush = time.monotonic_ns()
        functions = [partial(self.wait_for_timestamp_, flush),
                     self.capture_request_]
        return self.dispatch_functions(functions, wait, signal_function)

    def switch_mode_capture_request_and_stop(self, camera_config, wait=None, signal_function=None):
        """Switch the camera into a new (capture) mode, capture a request in the new mode and then stop the camera."""

        def capture_request_and_stop_(self):
            done, result = self.capture_request_()
            if not done:
                return (False, None)
            self.stop_()
            return (True, result)

        functions = [partial(self.switch_mode_, camera_config),
                     partial(capture_request_and_stop_, self)]
        return self.dispatch_functions(functions, wait, signal_function, immediate=True)

    @contextlib.contextmanager
    def captured_request(self, wait=None, flush=None):
        """Capture a completed request using the context manager which guarantees its release."""
        request = self.capture_request(wait=wait, flush=flush)
        try:
            yield request
        finally:
            request.release()

    @contextlib.contextmanager
    def captured_sync_request(self, wait=None):
        """Capture the first synchronised request using the context manager which guarantees its release.

        Only for use when running with the software sync algorith.
        """
        request = self.capture_sync_request(wait=wait)
        try:
            yield request
        finally:
            request.release()

    def capture_metadata_(self):
        if not self.completed_requests:
            return (False, None)
        request = self.completed_requests.pop(0)
        result = request.get_metadata()
        request.release()
        return (True, result)

    def capture_metadata(self, wait=None, signal_function=None):
        """Fetch the metadata from the next camera frame."""
        functions = [self.capture_metadata_]
        return self.dispatch_functions(functions, wait, signal_function)

    def capture_buffer_(self, name):
        if not self.completed_requests:
            return (False, None)
        request = self.completed_requests.pop(0)
        result = request.make_buffer(name)
        request.release()
        return (True, result)

    def capture_buffer(self, name="main", wait=None, signal_function=None):
        """Make a 1d numpy array from the next frame in the named stream."""
        return self.dispatch_functions([partial(self.capture_buffer_, name)], wait, signal_function)

    def capture_buffers_and_metadata_(self, names) -> Tuple[List[np.ndarray], dict]:
        if not self.completed_requests:
            return (False, None)
        request = self.completed_requests.pop(0)
        result = ([request.make_buffer(name) for name in names], request.get_metadata())
        request.release()
        return (True, result)

    def capture_buffers(self, names=["main"], wait=None, signal_function=None):
        """Make a 1d numpy array from the next frame for each of the named streams."""
        return self.dispatch_functions([partial(self.capture_buffers_and_metadata_, names)], wait, signal_function)

    def switch_mode_and_capture_buffer(self, camera_config, name="main", wait=None, signal_function=None, delay=0):
        """Switch the camera into a new (capture) mode, capture the first buffer.

        Then return back to the initial camera mode.
        """
        preview_config = self.camera_config

        def capture_buffer_and_switch_back_(self, preview_config, name):
            done, result = self.capture_buffer_(name)
            if not done:
                return (False, None)
            self.switch_mode_(preview_config)
            return (True, result)

        functions = [partial(self.switch_mode_, camera_config),
                     partial(self.set_frame_drops_, delay), self.drop_frames_,
                     partial(capture_buffer_and_switch_back_, self, preview_config, name)]
        return self.dispatch_functions(functions, wait, signal_function, immediate=True)

    def switch_mode_and_capture_buffers(self, camera_config, names=["main"], wait=None, signal_function=None, delay=0):
        """Switch the camera into a new (capture) mode, capture the first buffers.

        Then return back to the initial camera mode.
        """
        preview_config = self.camera_config

        def capture_buffers_and_switch_back_(self, preview_config, names):
            done, result = self.capture_buffers_and_metadata_(names)
            if not done:
                return (False, None)
            self.switch_mode_(preview_config)
            return (True, result)

        functions = [partial(self.switch_mode_, camera_config),
                     partial(self.set_frame_drops_, delay), self.drop_frames_,
                     partial(capture_buffers_and_switch_back_, self, preview_config, names)]
        return self.dispatch_functions(functions, wait, signal_function, immediate=True)

    def capture_array_(self, name):
        if not self.completed_requests:
            return (False, None)
        request = self.completed_requests.pop(0)
        result = request.make_array(name)
        request.release()
        return (True, result)

    def capture_array(self, name="main", wait=None, signal_function=None):
        """Make a 2d image from the next frame in the named stream."""
        return self.dispatch_functions([partial(self.capture_array_, name)], wait, signal_function)

    def capture_arrays_and_metadata_(self, names) -> Tuple[List[np.ndarray], Dict[str, Any]]:
        if not self.completed_requests:
            return (False, None)
        request = self.completed_requests.pop(0)
        result = ([request.make_array(name) for name in names], request.get_metadata())
        request.release()
        return (True, result)

    def capture_arrays(self, names=["main"], wait=None, signal_function=None):
        """Make 2d image arrays from the next frames in the named streams."""
        return self.dispatch_functions([partial(self.capture_arrays_and_metadata_, names)], wait, signal_function)

    def switch_mode_and_capture_array(self, camera_config, name="main", wait=None, signal_function=None, delay=0):
        """Switch the camera into a new (capture) mode, capture the image array data.

        Then return back to the initial camera mode.
        """
        preview_config = self.camera_config

        def capture_array_and_switch_back_(self, preview_config, name):
            done, result = self.capture_array_(name)
            if not done:
                return (False, None)
            self.switch_mode_(preview_config)
            return (True, result)

        functions = [partial(self.switch_mode_, camera_config),
                     partial(self.set_frame_drops_, delay), self.drop_frames_,
                     partial(capture_array_and_switch_back_, self, preview_config, name)]
        return self.dispatch_functions(functions, wait, signal_function, immediate=True)

    def switch_mode_and_capture_arrays(self, camera_config, names=["main"], wait=None, signal_function=None, delay=0):
        """Switch the camera into a new (capture) mode, capture the image arrays.

        Then return back to the initial camera mode.
        """
        preview_config = self.camera_config

        def capture_arrays_and_switch_back_(self, preview_config, names):
            done, result = self.capture_arrays_and_metadata_(names)
            if not done:
                return (False, None)
            self.switch_mode_(preview_config)
            return (True, result)

        functions = [partial(self.switch_mode_, camera_config),
                     partial(self.set_frame_drops_, delay), self.drop_frames_,
                     partial(capture_arrays_and_switch_back_, self, preview_config, names)]
        return self.dispatch_functions(functions, wait, signal_function, immediate=True)

    def capture_image_(self, name: str) -> Image.Image:
        """Capture image

        :param name: Stream name
        :type name: str
        """
        if not self.completed_requests:
            return (False, None)
        request = self.completed_requests.pop(0)
        result = request.make_image(name)
        request.release()
        return (True, result)

    def capture_image(self, name: str = "main", wait: bool = None, signal_function=None) -> Image.Image:
        """Make a PIL image from the next frame in the named stream.

        :param name: Stream name, defaults to "main"
        :type name: str, optional
        :param wait: Wait for the event loop to finish an operation and signal us, defaults to True
        :type wait: bool, optional
        :param signal_function: Callback, defaults to None
        :type signal_function: function, optional
        :return: PIL Image
        :rtype: Image.Image
        """
        return self.dispatch_functions([partial(self.capture_image_, name)], wait, signal_function)

    def switch_mode_and_capture_image(self, camera_config, name: str = "main", wait: bool = None,
                                      signal_function=None, delay=0) -> Image.Image:
        """Switch the camera into a new (capture) mode, capture the image.

        Then return back to the initial camera mode.
        """
        preview_config = self.camera_config

        def capture_image_and_switch_back_(self, preview_config, name) -> Image.Image:
            done, result = self.capture_image_(name)
            if not done:
                return (False, None)
            self.switch_mode_(preview_config)
            return (True, result)

        functions = [partial(self.switch_mode_, camera_config),
                     partial(self.set_frame_drops_, delay), self.drop_frames_,
                     partial(capture_image_and_switch_back_, self, preview_config, name)]
        return self.dispatch_functions(functions, wait, signal_function, immediate=True)

    def start_encoder(self, encoder=None, output=None, pts=None, quality=None, name=None) -> None:
        """Start encoder

        :param encoder: Sets encoder or uses existing, defaults to None
        :type encoder: Encoder, optional
        :raises RuntimeError: No encoder set or no stream
        """
        _encoder = None
        if encoder is not None:
            _encoder = encoder
        else:
            if len(self._encoders) > 1:
                raise RuntimeError("Multiple possible encoders, need to pass encoder")
            elif len(self._encoders) == 1:
                _encoder = list(self._encoders)[0]
        if _encoder is None:
            raise RuntimeError("No encoder specified")
        if output is not None:
            if isinstance(output, str):
                output = FileOutput(output, pts=pts)
            _encoder.output = output
        streams = self.camera_configuration()
        if name is None:
            name = self.encode_stream_name
        if streams.get(name, None) is None:
            raise RuntimeError(f"Encode stream {name} was not defined")
        _encoder.name = name
        _encoder.width, _encoder.height = streams[name]['size']
        _encoder.format = streams[name]['format']
        _encoder.stride = streams[name]['stride']
        # Also give the encoder a nominal framerate, which we'll peg at 30fps max
        # in case we only have a dummy value
        min_frame_duration = self.camera_ctrl_info["FrameDurationLimits"][1].min
        min_frame_duration = max(min_frame_duration, 33333)
        try:
            if _encoder.framerate is None:
                _encoder.framerate = 1000000 / min_frame_duration
        except AttributeError:
            pass
        _encoder.start(quality=quality)
        with self.lock:
            self._encoders.add(_encoder)

    def stop_encoder(self, encoders=None) -> None:
        """Stops the encoder"""
        remove = []
        if encoders is None:
            for encoder in self._encoders:
                encoder.stop()
                remove += [encoder]
        elif isinstance(encoders, Encoder):
            encoders.stop()
            remove += [encoders]
        elif isinstance(encoders, list) or isinstance(encoders, set):
            for encoder in encoders:
                encoder.stop()
                remove += [encoder]
        with self.lock:
            for encoder in remove:
                self._encoders.remove(encoder)

    @property
    def encoders(self) -> set[Encoder]:
        """Extract current Encoder objects

        :return: Set of encoders
        :rtype: set
        """
        return self._encoders

    @encoders.setter
    def encoders(self, value):
        """Set Encoder to be used

        :param value: Encoder to be set
        :type value: Encoder
        :raises RuntimeError: Fail to pass Encoder
        """
        if isinstance(value, Encoder):
            self._encoders.add(value)
        elif isinstance(value, set):
            self._encoders.update(value)
        else:
            raise RuntimeError("Must pass Encoder or set of")

    def start_recording(self, encoder, output, pts=None, config=None, quality=None, name=None) -> None:
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
        self.start_encoder(encoder, output, pts=pts, quality=quality, name=name)
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

    def start_and_capture_files(self, name: str = "image{:03d}.jpg",
                                initial_delay=1, preview_mode="preview",
                                capture_mode="still", num_files=1, delay=1,
                                show_preview=True, exif_data=None):
        """This function makes capturing multiple images more convenient.

        Should only be used in command line line applications (not from a Qt application, for example).
        If will configure the camera as requested and start it, switching between preview and still modes
        for capture. It supports the following parameters (all optional):

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

        exif_data - dictionary containing user defined exif data (based on `piexif`). This will
            overwrite existing exif information generated by picamera2.
        """
        if self.started:
            self.stop()
        if delay:
            # Show a preview between captures, so we will switch mode and back for each capture.
            self.configure(preview_mode)
            self.start(show_preview=show_preview)
            for i in range(num_files):
                time.sleep(initial_delay if i == 0 else delay)
                self.switch_mode_and_capture_file(capture_mode, name.format(i), exif_data=exif_data)
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
                self.capture_file(name.format(i), exif_data=exif_data)
                if i == num_files - 1:
                    break
                time.sleep(delay)
        self.stop()

    def start_and_capture_file(self, name="image.jpg", delay=1, preview_mode="preview",
                               capture_mode="still", show_preview=True, exif_data=None):
        """This function makes capturing a single image more convenient.

        Should only be used in command line line applications (not from a Qt application, for example).
        If will configure the camera as requested and start it, switching from the preview to the still
        mode for capture. It supports the following parameters (all optional):

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

        exif_data - dictionary containing user defined exif data (based on `piexif`). This will
            overwrite existing exif information generated by picamera2.
        """
        self.start_and_capture_files(name=name, initial_delay=delay, preview_mode=preview_mode,
                                     capture_mode=capture_mode, num_files=1,
                                     show_preview=show_preview,
                                     exif_data=exif_data)

    def start_and_record_video(self, output, encoder=None, config=None, quality=Quality.MEDIUM,
                               show_preview=False, duration=0, audio=False):
        """This function makes video recording more convenient.

        Should only be used in command line applications (not from a Qt application, for example).
        It will configure the camera if requested and start it. The following parameters are required:

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
        self.start_encoder(encoder=encoder, output=output, quality=quality)
        self.start(show_preview=show_preview)
        if duration:
            time.sleep(duration)
            self.stop_recording()

    def autofocus_cycle(self, wait=None, signal_function=None):
        """Switch autofocus to auto mode and run an autofocus cycle.

        Return True if the autofocus cycle focuses successuly, otherwise False.
        """
        self.set_controls({"AfMode": controls.AfModeEnum.Auto, "AfTrigger": controls.AfTriggerEnum.Start})

        def wait_for_af_state(self, states):
            if not self.completed_requests:
                return (False, None)
            af_state = self.completed_requests[0].get_metadata()['AfState']
            self.completed_requests.pop(0).release()
            return (af_state in states, af_state == controls.AfStateEnum.Focused)

        # First wait for the scan to start. Once we've seen that, the AF cycle may:
        # succeed, fail or could go back to Idle if it is cancelled.
        functions = [partial(wait_for_af_state, self, {controls.AfStateEnum.Scanning}),
                     partial(wait_for_af_state, self,
                             {controls.AfStateEnum.Focused, controls.AfStateEnum.Failed, controls.AfStateEnum.Idle})]
        return self.dispatch_functions(functions, wait, signal_function)

    def capture_sync_request(self, wait=None, signal_function=None):
        """Return the first request when the camera system has reached sychronisation point.

        This method can be used when this camera is the sychronisation server or client
        for the software sync algorithm.
        """

        def capture_sync_request_(self):
            if not self.completed_requests:
                return (False, None)
            req = self.completed_requests.pop(0)
            sync_ready = req.get_metadata().get('SyncReady', False)
            if not sync_ready:
                # Not yet synced. Discard this request and wait some more.
                req.release()
                return (False, None)
            # Sync achieved. Return this request.
            return (True, req)

        return self.dispatch_functions([partial(capture_sync_request_, self)], wait, signal_function)
