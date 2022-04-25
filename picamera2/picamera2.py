#!/usr/bin/python3

import os
import libcamera
import numpy as np
import threading
from PIL import Image
from picamera2.encoders.encoder import Encoder
import time
import tempfile
import json
from picamera2.utils.picamera2_logger import *
from picamera2.previews.null_preview import *
from picamera2.previews.drm_preview import *
from picamera2.previews.qt_preview import *
from picamera2.previews.qt_gl_preview import *
from enum import Enum
import piexif


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

    def _reset_flags(self):
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
        self.frames = 0
        self.functions = []
        self.event = threading.Event()
        self.asynchronous = False
        self.async_operation_in_progress = False
        self.asyc_result = None
        self.async_error = None
        self.controls_lock = threading.Lock()
        self.controls = {}
        self.options = {}
        self._encoder = None
        self.request_callback = None
        self.completed_requests = []
        self.lock = threading.Lock()  # protects the functions and completed_requests fields

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_traceback):
        self.close()

    def __del__(self):
        # Without this libcamera will complain if we shut down without closing the camera.
        self.log.debug(f"Resources now free: {self}")
        self.close()

    def initialize_camera(self):
        if isinstance(self.camera_idx, str):
            try:
                self.camera = self.camera_manager.get(self.camera_idx)
            except Exception:
                self.camera = self.camera_manager.find(self.camera_idx)
        elif isinstance(self.camera_idx, int):
            self.camera = self.camera_manager.cameras[self.camera_idx]
        if self.camera is not None:
            self.__identify_camera()
            self.camera_controls = self.camera.controls
            self.camera_properties = self.camera.properties

            # The next two lines could be placed elsewhere?
            self.sensor_resolution = self.camera.properties["PixelArraySize"]
            self.sensor_format = self.camera.generateConfiguration([RAW]).at(0).pixelFormat

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

    def open_camera(self):
        if self.initialize_camera():
            if self.camera.acquire() >= 0:
                self.is_open = True
                self.log.info("Camera now open.")
            else:
                raise RuntimeError("Failed to acquire camera")
        else:
            raise RuntimeError("Failed to initialize camera")

    def start_preview(self, preview=None, **kwargs):
        """
        Start the given preview which drives the camera processing. The preview
        may be either:
          None - in which case a NullPreview is made,
          a Preview enum value - in which case a preview of that type is made,
          or an actual preview object.

        When using the enum form, extra keyword arguments can be supplied that
        will be forwarded to the preview class constructor.
        """
        if self._preview:
            raise RuntimeError("A preview is already running")

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

    def stop_preview(self):
        if self._preview:
            try:
                self._preview.stop()
                del self._preview
                self._preview = None
                return True
            except Exception:
                raise RuntimeError("Unable to stop preview.")
        else:
            raise RuntimeError("No preview specified.")

    def close(self):
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

    def make_initial_stream_config(self, stream_config, updates):
        # Take an initial stream_config and add any user updates.
        if updates is None:
            return None
        if "format" in updates:
            stream_config["format"] = updates["format"]
        if "size" in updates:
            stream_config["size"] = updates["size"]
        return stream_config

    def preview_configuration(self, main={}, lores=None, raw=None, transform=libcamera.Transform(), colour_space=libcamera.ColorSpace.Jpeg(), buffer_count=4, controls={}):
        "Make a configuration suitable for camera preview."
        if self.camera is None:
            raise RuntimeError("Camera not opened")
        main = self.make_initial_stream_config({"format": "XBGR8888", "size": (640, 480)}, main)
        self.align_stream(main)
        lores = self.make_initial_stream_config({"format": "YUV420", "size": main["size"]}, lores)
        raw = self.make_initial_stream_config({"format": self.sensor_format, "size": main["size"]}, raw)
        controls = {"NoiseReductionMode": 3} | controls
        return {"use_case": "preview",
                "transform": transform,
                "colour_space": colour_space,
                "buffer_count": buffer_count,
                "main": main,
                "lores": lores,
                "raw": raw,
                "controls": controls}

    def still_configuration(self, main={}, lores=None, raw=None, transform=libcamera.Transform(), colour_space=libcamera.ColorSpace.Jpeg(), buffer_count=2, controls={}):
        "Make a configuration suitable for still image capture. Default to 2 buffers, as the Gl preview would need them."
        if self.camera is None:
            raise RuntimeError("Camera not opened")
        main = self.make_initial_stream_config({"format": "XBGR8888", "size": self.sensor_resolution}, main)
        self.align_stream(main)
        lores = self.make_initial_stream_config({"format": "YUV420", "size": main["size"]}, lores)
        raw = self.make_initial_stream_config({"format": self.sensor_format, "size": main["size"]}, raw)
        controls = {"NoiseReductionMode": 2} | controls
        return {"use_case": "still",
                "transform": transform,
                "colour_space": colour_space,
                "buffer_count": buffer_count,
                "main": main,
                "lores": lores,
                "raw": raw,
                "controls": controls}

    def video_configuration(self, main={}, lores=None, raw=None, transform=libcamera.Transform(), colour_space=None, buffer_count=6, controls={}):
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
        controls = {"NoiseReductionMode": 1, "FrameDurationLimits": (33333, 33333)} | controls
        return {"use_case": "video",
                "transform": transform,
                "colour_space": colour_space,
                "buffer_count": buffer_count,
                "main": main,
                "lores": lores,
                "raw": raw,
                "controls": controls}

    def check_stream_config(self, stream_config, name):
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

    def check_camera_config(self, camera_config):
        # Check the entire camera configuration for errors.
        if "colour_space" not in camera_config:
            raise RuntimeError("No colour space in camera configuration")
        if type(camera_config["colour_space"]) is not libcamera._libcamera.ColorSpace:
            raise RuntimeError("Colour space has incorrect type")
        if "transform" not in camera_config:
            raise RuntimeError("No transform in camera configuration")
        if type(camera_config["transform"]) is not libcamera._libcamera.Transform:
            raise RuntimeError("Transform has incorrect type")
        if "main" not in camera_config:
            raise RuntimeError("No main stream in camera configuration")
        if "lores" not in camera_config:
            raise RuntimeError("lores stream should be in configuration even if None")
        if "raw" not in camera_config:
            raise RuntimeError("raw stream should be in configuration even if None")
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

    def update_libcamera_stream_config(self, libcamera_stream_config, stream_config, buffer_count):
        # Update the libcamera stream config with ours.
        libcamera_stream_config.size = stream_config["size"]
        libcamera_stream_config.pixelFormat = stream_config["format"]
        libcamera_stream_config.bufferCount = buffer_count

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
        libcamera_config = self.camera.generateConfiguration(roles)
        libcamera_config.transform = camera_config["transform"]
        buffer_count = camera_config["buffer_count"]
        self.update_libcamera_stream_config(libcamera_config.at(self.main_index), camera_config["main"], buffer_count)
        libcamera_config.at(self.main_index).colorSpace = camera_config["colour_space"]
        if self.lores_index >= 0:
            self.update_libcamera_stream_config(libcamera_config.at(self.lores_index), camera_config["lores"], buffer_count)
            libcamera_config.at(self.lores_index).colorSpace = camera_config["colour_space"]
        if self.raw_index >= 0:
            self.update_libcamera_stream_config(libcamera_config.at(self.raw_index), camera_config["raw"], buffer_count)
            libcamera_config.at(self.raw_index).colorSpace = libcamera.ColorSpace.Raw()

        return libcamera_config

    def align_stream(self, stream_config):
        # Adjust the image size so that all planes are a mutliple of 32 bytes wide.
        # This matches the hardware behaviour and means we can be more efficient.
        align = 32
        if stream_config["format"] in ("YUV420", "YVU420"):
            align = 64  # because the UV planes will have half this alignment
        elif stream_config["format"] in ("XBGR8888", "XRGB8888"):
            align = 16  # 4 channels per pixel gives us an automatic extra factor of 2
        size = stream_config["size"]
        stream_config["size"] = (size[0] - size[0] % align, size[1] - size[1] % 2)

    def is_YUV(self, fmt):
        return fmt in ("NV21", "NV12", "YUV420", "YVU420", "YVYU", "YUYV", "UYVY", "VYUY")

    def is_RGB(self, fmt):
        return fmt in ("BGR888", "RGB888", "XBGR8888", "XRGB8888")

    def is_Bayer(self, fmt):
        return fmt in ("SBGGR10", "SGBRG10", "SGRBG10", "SRGGB10",
                       "SBGGR10_CSI2P", "SGBRG10_CSI2P", "SGRBG10_CSI2P", "SRGGB10_CSI2P",
                       "SBGGR12", "SGBRG12", "SGRBG12", "SRGGB12",
                       "SBGGR12_CSI2P", "SGBRG12_CSI2P", "SGRBG12_CSI2P", "SRGGB12_CSI2P")

    def make_requests(self):
        # Make libcamera request objects. Makes as many as the number of buffers in the
        # stream with the smallest number of buffers.
        num_requests = min([len(self.allocator.buffers(stream)) for stream in self.streams])
        requests = []
        for i in range(num_requests):
            request = self.camera.createRequest()
            if request is None:
                raise RuntimeError("Could not create request")

            for stream in self.streams:
                if request.addBuffer(stream, self.allocator.buffers(stream)[i]) < 0:
                    raise RuntimeError("Failed to set request buffer")

            requests.append(request)

        return requests

    def update_stream_config(self, stream_config, libcamera_stream_config):
        # Update our stream config from libcamera's.
        stream_config["format"] = libcamera_stream_config.pixelFormat
        stream_config["size"] = libcamera_stream_config.size
        stream_config["stride"] = libcamera_stream_config.stride
        stream_config["framesize"] = libcamera_stream_config.frameSize

    def update_camera_config(self, camera_config, libcamera_config):
        # Update our camera config from libcamera's.
        camera_config["transform"] = libcamera_config.transform
        camera_config["colour_space"] = libcamera_config.at(0).colorSpace
        self.update_stream_config(camera_config["main"], libcamera_config.at(0))
        if self.lores_index >= 0:
            self.update_stream_config(camera_config["lores"], libcamera_config.at(self.lores_index))
        if self.raw_index >= 0:
            self.update_stream_config(camera_config["raw"], libcamera_config.at(self.raw_index))

    def configure_(self, camera_config=None):
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
        if status == libcamera.ConfigurationStatus.Invalid:
            raise RuntimeError("Invalid camera configuration: {}".format(camera_config))
        elif status == libcamera.ConfigurationStatus.Adjusted:
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

        # These name the streams that we will display/encode. An application could change them.
        self.display_stream_name = "main"
        self.encode_stream_name = "main"

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

    def configure(self, camera_config=None):
        """Configure the camera system with the given configuration."""
        self.configure_(camera_config)

    def camera_configuration(self):
        """Return the camera configuration."""
        return self.camera_config

    def stream_configuration(self, name="main"):
        """Return the stream configuration for the named stream."""
        return self.camera_config[name]

    def list_controls(self):
        """List the controls supported by the camera."""
        return self.camera.controls

    def start_(self, controls={}):
        """Start the camera system running."""
        if self.camera_config is None:
            raise RuntimeError("Camera has not been configured")
        if self.started:
            raise RuntimeError("Camera already started")
        if self.camera.start(self.camera_config["controls"] | controls) >= 0:
            for request in self.make_requests():
                self.camera.queueRequest(request)
            self.log.info("Camera started")
            self.started = True
        else:
            self.log.error("Camera did not start properly.")
            raise RuntimeError("Camera did not start properly.")

    def start(self, controls={}):
        """Start the camera system running."""
        if self.camera_config is None:
            raise RuntimeError("Camera has not been configured")
        self.start_(controls)

    def stop_(self, request=None):
        """Stop the camera. Only call this function directly from within the camera event
        loop, such as in a Qt application."""
        if self.started:
            self.stop_count += 1
            self.camera.stop()
            self.camera_manager.getReadyRequests()  # Could anything here need flushing?
            self.started = False
            self.completed_requests = []
            self.log.info("Camera stopped")
        return True

    def stop(self):
        """Stop the camera."""
        if not self.started:
            self.log.debug("Camera was not started")
            return
        if self.asynchronous:
            self.dispatch_functions([self.stop_])
            self.wait()
        else:
            self.stop_()

    def set_controls(self, controls):
        """Set camera controls. These will be delivered with the next request that gets submitted."""
        with self.controls_lock:
            for key, value in controls.items():
                self.controls[key] = value

    def get_completed_requests(self):
        # Return all the requests that libcamera has completed.
        data = os.read(self.camera_manager.efd, 8)
        requests = [CompletedRequest(req, self) for req in self.camera_manager.getReadyRequests()
                    if req.status == libcamera.RequestStatus.Complete]
        self.frames += len(requests)
        return requests

    def process_requests(self):
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

            if self._encoder is not None:
                stream = self.stream_map[self.encode_stream_name]
                self._encoder.encode(stream, display_request)

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
                    if self.async_signal_function is None:
                        self.async_operation_in_progress = False
                    else:
                        self.async_signal_function(self)

            # We can only hang on to a limited number of requests here, most should be recycled
            # immediately back to libcamera. You could consider customising this number.
            while len(self.completed_requests) > 1:
                self.completed_requests.pop(0).release()

        # If one of the functions we ran stopped the camera, then we don't want
        # this going back to the application.
        if display_request.stop_count != self.stop_count:
            display_request.release()
            display_request = None

        # Some applications may (for example) want us to draw something onto these images before
        # showing them.
        if display_request and self.request_callback:
            self.request_callback(display_request)

        return display_request

    def wait(self):
        """Wait for the event loop to finish an operation and signal us."""
        if not self.async_operation_in_progress:
            raise RuntimeError("Waiting for non-existent operation!")
        self.event.wait()
        if self.event.is_set():
            self.event.clear()
            self.async_operation_in_progress = False
        if self.async_error:
            raise self.async_error
        return self.async_result

    def signal_event(self):
        self.event.set()

    def dispatch_functions(self, functions, signal_function=signal_event):
        """The main thread should use this to dispatch a number of operations for the event
        loop to perform. When there are multiple items each will be processed on a separate
        trip round the event loop, meaning that a single operation could stop and restart the
        camera and the next operation would receive a request from after the restart."""
        if self.async_operation_in_progress:
            raise RuntimeError("Failure to wait for previous operation to finish!")
        self.async_error = None
        self.async_result = None
        self.async_signal_function = signal_function
        self.functions = functions
        self.async_operation_in_progress = True

    def capture_file_(self, filename, name):
        request = self.completed_requests.pop(0)
        request.save(name, filename)
        self.async_result = request.get_metadata()
        request.release()
        return True

    def capture_file(self, filename, name="main", wait=True, signal_function=signal_event):
        """Capture an image to a file in the current camera mode."""
        with self.lock:
            if self.completed_requests:
                self.capture_file_(filename, name)
                return self.async_result
            else:
                self.dispatch_functions([(lambda: self.capture_file_(filename, name))], signal_function)
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

    def switch_mode_and_capture_file(self, camera_config, filename, name="main", wait=True, signal_function=signal_event):
        """Switch the camera into a new (capture) mode, capture an image to file, then return
        back to the initial camera mode."""
        preview_config = self.camera_config

        def capture_and_switch_back_(self, filename, preview_config):
            self.capture_file_(filename, name)
            self.switch_mode_(preview_config)
            return True

        functions = [(lambda: self.switch_mode_(camera_config)),
                     (lambda: capture_and_switch_back_(self, filename, preview_config))]
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
                return self.async_result
            else:
                self.dispatch_functions([(lambda: self.capture_buffer_(name))], signal_function)
        if wait:
            return self.wait()

    def switch_mode_and_capture_buffer(self, camera_config, name="main", wait=True, signal_function=signal_event):
        """Switch the camera into a new (capture) mode, capture the first buffer, then return
        back to the initial camera mode."""
        preview_config = self.camera_config

        def capture_buffer_and_switch_back_(self, preview_config, name):
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

    def capture_array_(self, name):
        request = self.completed_requests.pop(0)
        self.async_result = request.make_array(name)
        request.release()
        return True

    def capture_array(self, name="main", wait=True, signal_function=signal_event):
        """Make a 2d image from the next frame in the named stream."""
        with self.lock:
            if self.completed_requests:
                self.capture_array_(name)
                return self.async_result
            else:
                self.dispatch_functions([(lambda: self.capture_array_(name))], signal_function)
        if wait:
            return self.wait()

    def switch_mode_and_capture_array(self, camera_config, name="main", wait=True, signal_function=signal_event):
        """Switch the camera into a new (capture) mode, capture the image array data, then return
        back to the initial camera mode."""
        preview_config = self.camera_config

        def capture_array_and_switch_back_(self, preview_config, name):
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

    def capture_image_(self, name):
        request = self.completed_requests.pop(0)
        self.async_result = request.make_image(name)
        request.release()
        return True

    def capture_image(self, name="main", wait=True, signal_function=signal_event):
        """Make a PIL image from the next frame in the named stream."""
        with self.lock:
            if self.completed_requests:
                self.capture_image_(name)
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

    def start_encoder(self):
        streams = self.camera_configuration()
        if streams['use_case'] != "video":
            raise RuntimeError("No video stream found")
        if self.encoder is None:
            raise RuntimeError("No encoder specified")
        name = self.encode_stream_name
        self.encoder.width, self.encoder.height = streams[name]['size']
        self.encoder.format = streams[name]['format']
        self.encoder.stride = streams[name]['stride']
        self.encoder._start()

    def stop_encoder(self):
        self.encoder._stop()

    @property
    def encoder(self):
        return self._encoder

    @encoder.setter
    def encoder(self, value):
        if not isinstance(value, Encoder):
            raise RuntimeError("Must pass encoder instance")
        self._encoder = value

    def start_recording(self, encoder, output):
        """Start recording a video using the given encoder and to the given output.
        Output may be a string in which case the correspondingly named file is opened."""
        if isinstance(output, str):
            output = open(output, 'wb')
        encoder.output = output
        self.encoder = encoder
        self.start_encoder()
        self.start()

    def stop_recording(self):
        """Stop recording a video. The encode and output are stopped and closed."""
        self.stop()
        self.stop_encoder()
        self.encoder.output.close()

    def set_overlay(self, overlay):
        """Display an overlay on the camera image. The overlay may be either None,
        in which case any overlay is removed, or a 4-channel image, the last of the
        channels being taken as the alpha channel."""
        if overlay is None:
            pass  # OK
        else:
            shape = overlay.shape
            if len(shape) != 3 or shape[2] != 4:
                raise RuntimeError("Overlay must be a 4-channel image")
        self._preview.set_overlay(overlay)


class CompletedRequest:
    def __init__(self, request, picam2):
        self.request = request
        self.ref_count = 1
        self.lock = threading.Lock()
        self.picam2 = picam2
        self.stop_count = picam2.stop_count

    def acquire(self):
        """Acquire a reference to this completed request, which stops it being recycled back to
        the camera system."""
        with self.lock:
            if self.ref_count == 0:
                raise RuntimeError("CompletedRequest: acquiring lock with ref_count 0")
            self.ref_count += 1

    def release(self):
        """Release this completed frame back to the camera system (once its reference count
        reaches zero)."""
        with self.lock:
            self.ref_count -= 1
            if self.ref_count < 0:
                raise RuntimeError("CompletedRequest: lock now has negative ref_count")
            elif self.ref_count == 0:
                # If the camera has been stopped since this request was returned then we
                # can't recycle it.
                if self.stop_count == self.picam2.stop_count:
                    self.request.reuse()
                    with self.picam2.controls_lock:
                        for key, value in self.picam2.controls.items():
                            self.request.set_control(key, value)
                            self.picam2.controls = {}
                        self.picam2.camera.queueRequest(self.request)
                self.request = None

    def make_buffer(self, name):
        """Make a 1d numpy array from the named stream's buffer."""
        stream = self.picam2.stream_map[name]
        fb = self.request.buffers[stream]
        with fb.mmap(0) as b:
            return np.array(b, dtype=np.uint8)

    def get_metadata(self):
        """Fetch the metadata corresponding to this completed request."""
        return self.request.metadata

    def make_array(self, name):
        """Make a 2d numpy array from the named stream's buffer."""
        array = self.make_buffer(name)
        config = self.picam2.camera_config[name]
        fmt = config["format"]
        w, h = config["size"]
        stride = config["stride"]

        # Turning the 1d array into a 2d image-like array only works if the
        # image stride (which is in bytes) is a whole number of pixels. Even
        # then, if they don't match exactly you will get "padding" down the RHS.
        # Working around this requires another expensive copy of all the data.
        if fmt in ("BGR888", "RGB888"):
            if stride != w * 3:
                array = array.reshape((h, stride))
                array = np.asarray(array[:, :w * 3], order='C')
            image = array.reshape((h, w, 3))
        elif fmt in ("XBGR8888", "XRGB8888"):
            if stride != w * 4:
                array = array.reshape((h, stride))
                array = np.asarray(array[:, :w * 4], order='C')
            image = array.reshape((h, w, 4))
        elif fmt[0] == 'S':  # raw formats
            image = array.reshape((h, stride))
        else:
            raise RuntimeError("Format " + fmt + " not supported")
        return image

    def make_image(self, name, width=None, height=None):
        """Make a PIL image from the named stream's buffer."""
        rgb = self.make_array(name)
        fmt = self.picam2.camera_config[name]["format"]
        mode_lookup = {"RGB888": "BGR", "BGR888": "RGB", "XBGR8888": "RGBA", "XRGB8888": "BGRX"}
        mode = mode_lookup[fmt]
        pil_img = Image.frombuffer("RGB", (rgb.shape[1], rgb.shape[0]), rgb, "raw", mode, 0, 1)
        if width is None:
            width = rgb.shape[1]
        if height is None:
            height = rgb.shape[0]
        if width != rgb.shape[1] or height != rgb.shape[0]:
            # This will be slow. Consider requesting camera images of this size in the first place!
            pil_img = pil_img.resize((width, height))
        return pil_img

    def save(self, name, filename):
        """Save a JPEG or PNG image of the named stream's buffer."""
        # This is probably a hideously expensive way to do a capture.
        start_time = time.monotonic()
        img = self.make_image(name)
        exif = b''
        if filename.split('.')[-1].lower() in ('jpg', 'jpeg') and img.mode == "RGBA":
            # Nasty hack. Qt doesn't understand RGBX so we have to use RGBA. But saving a JPEG
            # doesn't like RGBA to we have to bodge that to RGBX.
            img.mode = "RGBX"
            # Make up some extra EXIF data.
            metadata = self.get_metadata()
            zero_ifd = {piexif.ImageIFD.Make: "Raspberry Pi",
                        piexif.ImageIFD.Model: self.picam2.camera.id,
                        piexif.ImageIFD.Software: "Picamera2"}
            total_gain = metadata["AnalogueGain"] * metadata["DigitalGain"]
            exif_ifd = {piexif.ExifIFD.ExposureTime: (metadata["ExposureTime"], 1000000),
                        piexif.ExifIFD.ISOSpeedRatings: int(total_gain * 100)}
            exif = piexif.dump({"0th": zero_ifd, "Exif": exif_ifd})
        # compress_level=1 saves pngs much faster, and still gets most of the compression.
        png_compress_level = self.picam2.options.get("compress_level", 1)
        jpeg_quality = self.picam2.options.get("quality", 90)
        img.save(filename, compress_level=png_compress_level, quality=jpeg_quality, exif=exif)
        end_time = time.monotonic()
        self.picam2.log.info(f"Saved {self} to file {filename}.")
        self.picam2.log.info(f"Time taken for encode: {(end_time-start_time)*1000} ms.")
