#!/usr/bin/python3

from enum import Enum
import json
import os
import tempfile
import threading
from typing import List

import libcamera
import numpy as np
from PIL import Image

from picamera2.encoders import Encoder
from picamera2.outputs import FileOutput
from picamera2.utils import initialize_logger
from picamera2.previews import NullPreview, DrmPreview, QtPreview, QtGlPreview
from .request import CompletedRequest


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
        """Load the named tuning file. If dir is given, then only that directory is checked,
        otherwise a list of likely installation directories is searched."""
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

    def __init__(self, camera_num=0, verbose_console=None, tuning=None):
        """Initialise camera system and open the camera for use."""
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
        try:
            self.open_camera()
            self.log.debug(f"{self.camera_manager}")
        except Exception:
            self.log.error("Camera __init__ sequence did not complete.")
            raise RuntimeError("Camera __init__ sequence did not complete.")
        finally:
            if tuning_file is not None:
                tuning_file.close()  # delete the temporary file

    def _reset_flags(self) -> None:
        self.camera = None
        self.is_open = False
        self.camera_controls = None
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
        self.event = threading.Event()
        self.async_operation_in_progress = False
        self.asyc_result = None
        self.async_error = None
        self.controls_lock = threading.Lock()
        self.controls = {}
        self.options = {}
        self._encoder = None
        self.pre_callback = None
        self.post_callback = None
        self.completed_requests = []
        self.lock = threading.Lock()  # protects the functions and completed_requests fields
        self.have_event_loop = False

    @property
    def request_callback(self):
        self.log.error("request_callback is deprecated, returning post_callback instead")
        return self.post_callback

    @request_callback.setter
    def request_callback(self, value):
        self.log.error("request_callback is deprecated, setting post_callback instead")
        self.post_callback = value

    @property
    def asynchronous(self) -> bool:
        """True if there is threaded operation."""
        return self._preview is not None and getattr(self._preview, "thread", None) is not None and self._preview.thread.is_alive()

    @property
    def camera_properties(self) -> dict:
        return {} if self.camera is None else self.camera.properties

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_traceback):
        self.close()

    def __del__(self):
        # Without this libcamera will complain if we shut down without closing the camera.
        self.log.debug(f"Resources now free: {self}")
        self.close()

    def initialize_camera(self) -> bool:
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
            self.camera_controls = self.camera.controls

            # The next two lines could be placed elsewhere?
            self.sensor_resolution = self.camera.properties["PixelArraySize"]
            self.sensor_format = self.camera.generate_configuration([RAW]).at(0).pixel_format

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

    def open_camera(self) -> None:
        if self.initialize_camera():
            if self.camera.acquire() >= 0:
                self.is_open = True
                self.log.info("Camera now open.")
            else:
                raise RuntimeError("Failed to acquire camera")
        else:
            raise RuntimeError("Failed to initialize camera")

    def start_preview(self, preview=None, **kwargs) -> None:
        """
        Start the given preview which drives the camera processing. The preview
        may be either:
          None - in which case a NullPreview is made,
          a Preview enum value - in which case a preview of that type is made,
          or an actual preview object.

        When using the enum form, extra keyword arguments can be supplied that
        will be forwarded to the preview class constructor.
        """
        if self.have_event_loop:
            raise RuntimeError("An event loop is already running")

        if preview is None:
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
            self.log.info(f'Camera closed successfully.')

    def make_initial_stream_config(self, stream_config: dict, updates: dict) -> dict:
        # Take an initial stream_config and add any user updates.
        if updates is None:
            return None
        valid = ("format", "size")
        for key, value in updates.items():
            if key in valid:
                stream_config[key] = value
            else:
                raise ValueError(f"Bad key '{key}': valid stream configuration keys are {valid}")
        return stream_config

    def add_display_and_encode(self, config, display, encode) -> None:
        if display is not None and config.get(display, None) is None:
            raise RuntimeError(f"Display stream {display} was not defined")
        if encode is not None and config.get(encode, None) is None:
            raise RuntimeError(f"Encode stream {encode} was not defined")
        config['display'] = display
        config['encode'] = encode

    def preview_configuration(self, main={}, lores=None, raw=None, transform=libcamera.Transform(), colour_space=libcamera.ColorSpace.Jpeg(), buffer_count=4, controls={}, display="main", encode="main"):
        "Make a configuration suitable for camera preview."
        if self.camera is None:
            raise RuntimeError("Camera not opened")
        main = self.make_initial_stream_config({"format": "XBGR8888", "size": (640, 480)}, main)
        self.align_stream(main)
        lores = self.make_initial_stream_config({"format": "YUV420", "size": main["size"]}, lores)
        raw = self.make_initial_stream_config({"format": self.sensor_format, "size": main["size"]}, raw)
        # Let the framerate vary from 12fps to as fast as possible.
        controls = {"NoiseReductionMode": libcamera.NoiseReductionMode.Minimal,
                    "FrameDurationLimits": (self.camera_controls["FrameDurationLimits"][0], 83333)} | controls
        config = {"use_case": "preview",
                  "transform": transform,
                  "colour_space": colour_space,
                  "buffer_count": buffer_count,
                  "main": main,
                  "lores": lores,
                  "raw": raw,
                  "controls": controls}
        self.add_display_and_encode(config, display, encode)
        return config

    def still_configuration(self, main={}, lores=None, raw=None, transform=libcamera.Transform(), colour_space=libcamera.ColorSpace.Jpeg(), buffer_count=1, controls={}, display=None, encode=None) -> dict:
        "Make a configuration suitable for still image capture. Default to 2 buffers, as the Gl preview would need them."
        if self.camera is None:
            raise RuntimeError("Camera not opened")
        main = self.make_initial_stream_config({"format": "BGR888", "size": self.sensor_resolution}, main)
        self.align_stream(main)
        lores = self.make_initial_stream_config({"format": "YUV420", "size": main["size"]}, lores)
        raw = self.make_initial_stream_config({"format": self.sensor_format, "size": main["size"]}, raw)
        # Let the framerate span the entire possible range of the sensor.
        controls = {"NoiseReductionMode": libcamera.NoiseReductionMode.HighQuality,
                    "FrameDurationLimits": self.camera_controls["FrameDurationLimits"][0:1]} | controls
        config = {"use_case": "still",
                  "transform": transform,
                  "colour_space": colour_space,
                  "buffer_count": buffer_count,
                  "main": main,
                  "lores": lores,
                  "raw": raw,
                  "controls": controls}
        self.add_display_and_encode(config, display, encode)
        return config

    def video_configuration(self, main={}, lores=None, raw=None, transform=libcamera.Transform(), colour_space=None, buffer_count=6, controls={}, display="main", encode="main") -> dict:
        "Make a configuration suitable for video recording."
        if self.camera is None:
            raise RuntimeError("Camera not opened")
        main = self.make_initial_stream_config({"format": "XBGR8888", "size": (1280, 720)}, main)
        self.align_stream(main)
        lores = self.make_initial_stream_config({"format": "YUV420", "size": main["size"]}, lores)
        raw = self.make_initial_stream_config({"format": self.sensor_format, "size": main["size"]}, raw)
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
        controls = {"NoiseReductionMode": libcamera.NoiseReductionMode.Fast,
                    "FrameDurationLimits": (33333, 33333)} | controls
        config = {"use_case": "video",
                  "transform": transform,
                  "colour_space": colour_space,
                  "buffer_count": buffer_count,
                  "main": main,
                  "lores": lores,
                  "raw": raw,
                  "controls": controls}
        self.add_display_and_encode(config, display, encode)
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
            if not self.is_Bayer(format):
                raise RuntimeError("Unrecognised raw format " + format)
        else:
            if not self.is_YUV(format) and not self.is_RGB(format):
                raise RuntimeError("Bad format " + format + " in stream " + name)
        if type(stream_config["size"]) is not tuple or len(stream_config["size"]) != 2:
            raise RuntimeError("size in " + name + " stream should be (width, height)")

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

    def update_libcamera_stream_config(self, libcamera_stream_config, stream_config, buffer_count) -> None:
        # Update the libcamera stream config with ours.
        libcamera_stream_config.size = stream_config["size"]
        libcamera_stream_config.pixel_format = stream_config["format"]
        libcamera_stream_config.buffer_count = buffer_count

    def make_libcamera_config(self, camera_config):
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
        self.update_libcamera_stream_config(libcamera_config.at(self.main_index), camera_config["main"], buffer_count)
        libcamera_config.at(self.main_index).color_space = camera_config["colour_space"]
        if self.lores_index >= 0:
            self.update_libcamera_stream_config(libcamera_config.at(self.lores_index), camera_config["lores"], buffer_count)
            libcamera_config.at(self.lores_index).color_space = camera_config["colour_space"]
        if self.raw_index >= 0:
            self.update_libcamera_stream_config(libcamera_config.at(self.raw_index), camera_config["raw"], buffer_count)
            libcamera_config.at(self.raw_index).color_space = libcamera.ColorSpace.Raw()

        return libcamera_config

    def align_stream(self, stream_config: dict) -> None:
        # Adjust the image size so that all planes are a mutliple of 32 bytes wide.
        # This matches the hardware behaviour and means we can be more efficient.
        align = 32
        if stream_config["format"] in ("YUV420", "YVU420"):
            align = 64  # because the UV planes will have half this alignment
        elif stream_config["format"] in ("XBGR8888", "XRGB8888"):
            align = 16  # 4 channels per pixel gives us an automatic extra factor of 2
        size = stream_config["size"]
        stream_config["size"] = (size[0] - size[0] % align, size[1] - size[1] % 2)

    def is_YUV(self, fmt) -> bool:
        return fmt in ("NV21", "NV12", "YUV420", "YVU420", "YVYU", "YUYV", "UYVY", "VYUY")

    def is_RGB(self, fmt) -> bool:
        return fmt in ("BGR888", "RGB888", "XBGR8888", "XRGB8888")

    def is_Bayer(self, fmt) -> bool:
        return fmt in ("SBGGR10", "SGBRG10", "SGRBG10", "SRGGB10",
                       "SBGGR10_CSI2P", "SGBRG10_CSI2P", "SGRBG10_CSI2P", "SRGGB10_CSI2P",
                       "SBGGR12", "SGBRG12", "SGRBG12", "SRGGB12",
                       "SBGGR12_CSI2P", "SGBRG12_CSI2P", "SGRBG12_CSI2P", "SRGGB12_CSI2P")

    def make_requests(self) -> List[libcamera.Request]:
        # Make libcamera request objects. Makes as many as the number of buffers in the
        # stream with the smallest number of buffers.
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

    def update_stream_config(self, stream_config, libcamera_stream_config) -> None:
        # Update our stream config from libcamera's.
        stream_config["format"] = libcamera_stream_config.pixel_format
        stream_config["size"] = libcamera_stream_config.size
        stream_config["stride"] = libcamera_stream_config.stride
        stream_config["framesize"] = libcamera_stream_config.frame_size

    def update_camera_config(self, camera_config, libcamera_config) -> None:
        # Update our camera config from libcamera's.
        camera_config["transform"] = libcamera_config.transform
        camera_config["colour_space"] = libcamera_config.at(0).color_space
        self.update_stream_config(camera_config["main"], libcamera_config.at(0))
        if self.lores_index >= 0:
            self.update_stream_config(camera_config["lores"], libcamera_config.at(self.lores_index))
        if self.raw_index >= 0:
            self.update_stream_config(camera_config["raw"], libcamera_config.at(self.raw_index))

    def configure_(self, camera_config=None) -> None:
        """Configure the camera system with the given configuration."""
        if self.started:
            raise RuntimeError("Camera must be stopped before configuring")
        if camera_config is None:
            camera_config = self.preview_configuration()

        # Mark ourselves as unconfigured.
        self.libcamera_config = None
        self.camera_config = None

        # Check the config and turn it into a libcamera config.
        self.check_camera_config(camera_config)
        libcamera_config = self.make_libcamera_config(camera_config)

        # Check that libcamera is happy with it.
        status = libcamera_config.validate()
        self.update_camera_config(camera_config, libcamera_config)
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
        # Set the controls directly so as to overwrite whatever is there. No need for the lock
        # here as the camera is not running. Copy it so that subsequent calls to set_controls
        # don't become part of the camera_config.
        self.controls = self.camera_config['controls'].copy()
        self.configure_count += 1

    def configure(self, camera_config=None) -> None:
        """Configure the camera system with the given configuration."""
        self.configure_(camera_config)

    def camera_configuration(self) -> dict:
        """Return the camera configuration."""
        return self.camera_config

    def stream_configuration(self, name="main") -> dict:
        """Return the stream configuration for the named stream."""
        return self.camera_config[name]

    def list_controls(self):
        """List the controls supported by the camera."""
        return self.camera.controls

    def start_(self) -> None:
        """Start the camera system running."""
        if self.camera_config is None:
            raise RuntimeError("Camera has not been configured")
        if self.started:
            raise RuntimeError("Camera already started")
        if self.camera.start(self.controls) >= 0:
            for request in self.make_requests():
                self.camera.queue_request(request)
            self.log.info("Camera started")
            self.started = True
        else:
            self.log.error("Camera did not start properly.")
            raise RuntimeError("Camera did not start properly.")

    def start(self, event_loop=True) -> None:
        """Start the camera system running. Camera controls may be sent to the
        camera before it starts running.

        Additionally the event_loop parameter will cause an event loop
        to be started if there is not one running already. In this
        case the event loop will not display a window of any kind. Applications
        wanting a preview window should use start_preview before calling this
        function.

        An application could elect not to start an event loop at all,
        in which in which case they would have to supply their own."""
        if self.camera_config is None:
            raise RuntimeError("Camera has not been configured")
        # By default we will create an event loop is there isn't one running already.
        if event_loop and not self.have_event_loop:
            self.start_preview(Preview.NULL)
        self.start_()

    def stop_(self, request=None) -> None:
        """Stop the camera. Only call this function directly from within the camera event
        loop, such as in a Qt application."""
        if self.started:
            self.stop_count += 1
            self.camera.stop()
            self.camera_manager.get_ready_requests()  # Could anything here need flushing?
            self.started = False
            self.completed_requests = []
            self.log.info("Camera stopped")
        return True

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
        with self.controls_lock:
            for key, value in controls.items():
                self.controls[key] = value

    def get_completed_requests(self) -> List[CompletedRequest]:
        # Return all the requests that libcamera has completed.
        data = os.read(self.camera_manager.efd, 8)
        requests = [CompletedRequest(req, self) for req in self.camera_manager.get_ready_requests()
                    if req.status == libcamera.Request.Status.Complete]
        self.frames += len(requests)
        return requests

    def process_requests(self) -> None:
        # This is the function that the event loop, which runs externally to us, must
        # call.
        requests = self.get_completed_requests()
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
                if function():
                    self.functions = self.functions[1:]
                # Once we've done everything, signal the fact to the thread that requested this work.
                if not self.functions:
                    if not self.async_operation_in_progress:
                        raise RuntimeError("Waiting for non-existent asynchronous operation")
                    self.async_operation_in_progress = False
                    if self.async_signal_function is not None:
                        self.async_signal_function(self)

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

    def wait(self) -> None:
        """Wait for the event loop to finish an operation and signal us."""
        self.event.wait()
        if self.event.is_set():
            self.event.clear()
        if self.async_error:
            raise self.async_error
        return self.async_result

    def signal_event(self) -> None:
        self.event.set()

    def dispatch_functions(self, functions, signal_function=signal_event) -> None:
        """The main thread should use this to dispatch a number of operations for the event
        loop to perform. When there are multiple items each will be processed on a separate
        trip round the event loop, meaning that a single operation could stop and restart the
        camera and the next operation would receive a request from after the restart."""
        if self.async_operation_in_progress:
            raise RuntimeError("Failure to wait for previous operation to finish!")
        self.event.clear()
        self.async_error = None
        self.async_result = None
        self.async_signal_function = signal_function
        self.functions = functions
        self.async_operation_in_progress = True

    def capture_file_(self, file_output, name, format=None):
        request = self.completed_requests.pop(0)
        if name == "raw" and self.is_Bayer(self.camera_config["raw"]["format"]):
            request.save_dng(file_output)
        else:
            request.save(name, file_output, format=format)

        self.async_result = request.get_metadata()
        request.release()
        return True

    def capture_file(self, file_output, name="main", format=None, wait=True, signal_function=signal_event):
        """Capture an image to a file in the current camera mode."""
        with self.lock:
            if self.completed_requests:
                self.capture_file_(file_output, name, format=format)
                if signal_function is not None:
                    signal_function(self)
                return self.async_result
            else:
                self.dispatch_functions([(lambda: self.capture_file_(file_output, name, format=format))], signal_function)
        if wait:
            return self.wait()

    def switch_mode_(self, camera_config):
        self.stop_()
        self.configure_(camera_config)
        self.start_()
        self.async_result = self.camera_config
        return True

    def switch_mode(self, camera_config, wait=True, signal_function=signal_event):
        """Switch the camera into another mode given by the camera_config."""
        functions = [(lambda: self.switch_mode_(camera_config))]
        self.dispatch_functions(functions, signal_function)
        if wait:
            return self.wait()

    def switch_mode_and_capture_file(self, camera_config, file_output, name="main", format=None, wait=True, signal_function=signal_event):
        """Switch the camera into a new (capture) mode, capture an image to file, then return
        back to the initial camera mode."""
        preview_config = self.camera_config

        def capture_and_switch_back_(self, file_output, preview_config, format):
            self.capture_file_(file_output, name, format=format)
            self.switch_mode_(preview_config)
            return True

        functions = [(lambda: self.switch_mode_(camera_config)),
                     (lambda: capture_and_switch_back_(self, file_output, preview_config, format))]
        self.dispatch_functions(functions, signal_function)
        if wait:
            return self.wait()

    def capture_request_(self):
        self.async_result = self.completed_requests.pop(0)
        # The "use" of this request is transferred from the completed_requests list to the caller.
        return True

    def capture_request(self, wait=True, signal_function=signal_event):
        """Fetch the next completed request from the camera system. You will be holding a
        reference to this request so you must release it again to return it to the camera system."""
        with self.lock:
            if self.completed_requests:
                self.capture_request_()
                if signal_function is not None:
                    signal_function(self)
                return self.async_result
            else:
                self.dispatch_functions([self.capture_request_], signal_function)
        if wait:
            return self.wait()

    def switch_mode_capture_request_and_stop(self, camera_config, wait=True, signal_function=signal_event):
        """Switch the camera into a new (capture) mode, capture a request in the new mode and then stop the camera."""

        def capture_request_and_stop_(self):
            self.capture_request_()
            request = self.async_result
            self.stop_()
            self.async_result = request
            return True

        functions = [(lambda: self.switch_mode_(camera_config)),
                     (lambda: capture_request_and_stop_(self))]
        self.dispatch_functions(functions, signal_function)
        if wait:
            return self.wait()

    def capture_metadata_(self):
        request = self.completed_requests.pop(0)
        self.async_result = request.get_metadata()
        request.release()
        return True

    def capture_metadata(self, wait=True, signal_function=signal_event):
        """Fetch the metadata from the next camera frame."""
        with self.lock:
            if self.completed_requests:
                self.capture_metadata_()
                if signal_function is not None:
                    signal_function(self)
                return self.async_result
            else:
                self.dispatch_functions([self.capture_metadata_], signal_function)
        if wait:
            return self.wait()

    def capture_buffer_(self, name):
        request = self.completed_requests.pop(0)
        self.async_result = request.make_buffer(name)
        request.release()
        return True

    def capture_buffer(self, name="main", wait=True, signal_function=signal_event):
        """Make a 1d numpy array from the next frame in the named stream."""
        with self.lock:
            if self.completed_requests:
                self.capture_buffer_(name)
                if signal_function is not None:
                    signal_function(self)
                return self.async_result
            else:
                self.dispatch_functions([(lambda: self.capture_buffer_(name))], signal_function)
        if wait:
            return self.wait()

    def switch_mode_and_capture_buffer(self, camera_config, name="main", wait=True, signal_function=signal_event):
        """Switch the camera into a new (capture) mode, capture the first buffer, then return
        back to the initial camera mode."""
        preview_config = self.camera_config

        def capture_buffer_and_switch_back_(self, preview_config, name) -> bool:
            self.capture_buffer_(name)
            buffer = self.async_result
            self.switch_mode_(preview_config)
            self.async_result = buffer
            return True

        functions = [(lambda: self.switch_mode_(camera_config)),
                     (lambda: capture_buffer_and_switch_back_(self, preview_config, name))]
        self.dispatch_functions(functions, signal_function)
        if wait:
            return self.wait()

    def capture_array_(self, name) -> bool:
        request = self.completed_requests.pop(0)
        self.async_result = request.make_array(name)
        request.release()
        return True

    def capture_array(self, name="main", wait=True, signal_function=signal_event) -> np.ndarray:
        """Make a 2d image from the next frame in the named stream."""
        with self.lock:
            if self.completed_requests:
                self.capture_array_(name)
                if signal_function is not None:
                    signal_function(self)
                return self.async_result
            else:
                self.dispatch_functions([(lambda: self.capture_array_(name))], signal_function)
        if wait:
            return self.wait()

    def switch_mode_and_capture_array(self, camera_config, name="main", wait=True, signal_function=signal_event):
        """Switch the camera into a new (capture) mode, capture the image array data, then return
        back to the initial camera mode."""
        preview_config = self.camera_config

        def capture_array_and_switch_back_(self, preview_config, name) -> bool:
            self.capture_array_(name)
            array = self.async_result
            self.switch_mode_(preview_config)
            self.async_result = array
            return True

        functions = [(lambda: self.switch_mode_(camera_config)),
                     (lambda: capture_array_and_switch_back_(self, preview_config, name))]
        self.dispatch_functions(functions, signal_function)
        if wait:
            return self.wait()

    def capture_image_(self, name) -> None:
        request = self.completed_requests.pop(0)
        self.async_result = request.make_image(name)
        request.release()

    def capture_image(self, name="main", wait=True, signal_function=signal_event) -> Image:
        """Make a PIL image from the next frame in the named stream."""
        with self.lock:
            if self.completed_requests:
                self.capture_image_(name)
                if signal_function is not None:
                    signal_function(self)
                return self.async_result
            else:
                self.dispatch_functions([(lambda: self.make_image_(name))], signal_function)
        if wait:
            return self.wait()

    def switch_mode_and_capture_image(self, camera_config, name="main", wait=True, signal_function=signal_event):
        """Switch the camera into a new (capture) mode, capture the image, then return
        back to the initial camera mode."""
        preview_config = self.camera_config

        def capture_image_and_switch_back_(self, preview_config, name):
            self.capture_image_(name)
            image = self.async_result
            self.switch_mode_(preview_config)
            self.async_result = image
            return True

        functions = [(lambda: self.switch_mode_(camera_config)),
                     (lambda: capture_image_and_switch_back_(self, preview_config, name))]
        self.dispatch_functions(functions, signal_function)
        if wait:
            return self.wait()

    def start_encoder(self, encoder=None) -> None:
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
        self.encoder._start()

    def stop_encoder(self) -> None:
        self.encoder._stop()

    @property
    def encoder(self):
        return self._encoder

    @encoder.setter
    def encoder(self, value):
        if not isinstance(value, Encoder):
            raise RuntimeError("Must pass encoder instance")
        self._encoder = value

    def start_recording(self, encoder, output) -> None:
        """Start recording a video using the given encoder and to the given output.
        Output may be a string in which case the correspondingly named file is opened."""
        if isinstance(output, str):
            output = FileOutput(output)
        encoder.output = output
        self.encoder = encoder
        self.start_encoder()
        self.start()

    def stop_recording(self) -> None:
        """Stop recording a video. The encode and output are stopped and closed."""
        self.stop()
        self.stop_encoder()

    def set_overlay(self, overlay) -> None:
        """Display an overlay on the camera image.

        The overlay may be either None, in which case any overlay is removed,
        or a 4-channel ``ndarray``, the last of thechannels being taken as the alpha channel."""
        if overlay is not None:
            if overlay.ndim != 3 or overlay.shape[2] != 4:
                raise RuntimeError("Overlay must be a 4-channel image")
        self._preview.set_overlay(overlay)
