#!/usr/bin/python3

import os
import libcamera
import numpy as np
import threading
from PIL import Image
from encoder import Encoder
import time


class Picamera2:
    """Picamera2 class"""

    def __init__(self, camera_num=0, verbose=1):
        """Initialise camera system and acquire the camera for use."""
        self.camera_manager = libcamera.CameraManager.singleton()
        self.verbose = verbose
        self.cm = libcamera.CameraManager.singleton()
        self.cidx = camera_num
            self.log.debug(f"{self.cm}")
        self.camera = None
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
        self.lock = threading.Lock() # protects the functions and completed_requests fields

        
        self.verbose_print("Camera manager:", self.camera_manager)
        self.verbose_print("Made", self)

        self.open_camera(camera_num)

    def verbose_print(self, *args):
        if self.verbose > 0:
            print(*args)

    def __enter__(self):
        return self

    def __exit__(self,exc_type, exc_val, exc_traceback):
        self.close_camera()

    def __del__(self):
        """Free any resources that are held."""
        self.verbose_print("Freeing resources for", self)
        self.close_camera()
    def initialize_camera(self):
        if isinstance(self.cidx,str):
            try:
                self.camera = self.cm.get(self.cidx)
            except:
                self.camera = self.cm.find(self.cidx)
        elif isinstance(self.cidx,int):
            self.camera = self.cm.cameras[self.cidx]
        if self.camera is not None:
            self.__identify_camera()
            self.default_controls = self.camera.controls
            self.camera_properties = self.camera.properties

            #The next two lines could be placed elsewhere?
            self.sensor_resolution = self.camera.properties["PixelArraySize"]
            self.sensor_format = self.camera.generateConfiguration([RAW]).at(0).pixelFormat

            self.log.info('Initialization successful.')
            return True
        else:
            self.log.error("Initialization failed.")
            raise RuntimeError("Initialization failed.")

    def __identify_camera(self):
        self.cid = self.camera.id
        for idx, address in enumerate(self.cm.cameras):
            if address == self.camera:
                self.cidx = idx
                break

    def acquire_camera(self):
        status = self.camera.acquire()
        if status >= 0:
            self.is_acquired = True
            self.log.info("Camera acquired.")
            return True
        else:
            raise RuntimeError("Failed to acquire camera {} ({})".format(
                camera_num, self.camera_manager.cameras[camera_num]))

        self.sensor_resolution = camera.properties["PixelArraySize"]
        self.sensor_format = camera.generateConfiguration([libcamera.StreamRole.Raw]).at(0).pixelFormat

    def close_camera(self):
        # Release this camera for use by others.
        if self.started:
            self.stop()
        if self.camera is not None:
            self.verbose_print("Closing camera:", self.camera)
            self.camera.release()
            self.camera = None
            self.verbose_print("Camera closed")

        self.cm.getReadyRequests()  # Could anything here need flushing?
        self.camera_config = None
        self.libcamera_config = None
        self.streams = None
        self.stream_map = None

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
        "Make a configuration suitable for still video recording."
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
        roles = [libcamera.StreamRole.Viewfinder]
        index = 1
        self.main_index = 0
        self.lores_index = -1
        self.raw_index = -1
        if camera_config["lores"] is not None:
            self.lores_index = index
            index += 1
            roles += [libcamera.StreamRole.Viewfinder]
        if camera_config["raw"] is not None:
            self.raw_index = index
            roles += [libcamera.StreamRole.Raw]

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
            align = 64 # because the UV planes will have half this alignment
        elif stream_config["format"] in ("XBGR8888", "XRGB8888"):
            align = 16 # 4 channels per pixel gives us an automatic extra factor of 2
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
        self.verbose_print("Requesting configuration:", camera_config)
        if status == libcamera.ConfigurationStatus.Invalid:
            raise RuntimeError("Invalid camera configuration: {}".format(camera_config))
        elif status == libcamera.ConfigurationStatus.Adjusted:
            self.verbose_print("Camera configuration has been adjusted!")

        # Configure libcamera.
        if self.camera.configure(libcamera_config):
            raise RuntimeError("Configuration failed: {}".format(camera_config))
        self.verbose_print("Configuration successful!")
        self.verbose_print("Final configuration:", camera_config)

        # Record which libcamera stream goes with which of our names.
        self.stream_map = {"main": libcamera_config.at(0).stream}
        self.stream_map["lores"] = libcamera_config.at(self.lores_index).stream if self.lores_index >= 0 else None
        self.stream_map["raw"] = libcamera_config.at(self.raw_index).stream if self.raw_index >= 0 else None
        self.verbose_print("Streams:", self.stream_map)

        # These name the streams that we will display/encode. An application could change them.
        self.display_stream_name = "main"
        self.encode_stream_name = "main"

        # Allocate all the frame buffers.
        self.streams = [stream_config.stream for stream_config in libcamera_config]
        self.allocator = libcamera.FrameBufferAllocator(self.camera)
        for i, stream in enumerate(self.streams):
            if self.allocator.allocate(stream) < 0:
                raise RuntimeError("Failed to allocate buffers")
            self.verbose_print("Allocated", len(self.allocator.buffers(stream)), "buffers for stream", i)

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
        if self.camera is None:
            raise RuntimeError("Camera has not been opened")
        if self.camera_config is None:
            raise RuntimeError("Camera has not been configured")
        if self.started:
            raise RuntimeError("Camera already started")
        self.camera.start(self.camera_config["controls"] | controls)
        for request in self.make_requests():
            self.camera.queueRequest(request)
        self.verbose_print("Camera started")
        self.started = True

    def start(self, controls={}):
        """Start the camera system running."""
        self.start_(controls)

    def stop_(self, request=None):
        # Stop the camera.
        self.camera.stop()
        self.camera_manager.getReadyRequests()  # Could anything here need flushing?
        self.started = False
        self.stop_count += 1
        self.completed_requests = []
        self.verbose_print("Camera stopped")
        return True

    def stop(self):
        """Stop the camera."""
        if not self.started:
            raise RuntimeError("Camera was not started")
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
        data = os.read(self.cm.efd, 8)
        requests = [CompletedRequest(req, self) for req in self.cm.getReadyRequests()
                    if req.status == libcamera.RequestStatus.Complete]
        self.frames += len(requests)
        return requests

    def process_requests(self):
        # This is the function that the event loop, which returns externally to us, must
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
                stream = self.stream_map["main"]
                self._encoder.encode(stream, display_request)

            # See if any actions have been queued up for us to do here.
            # Each operation is regarded as completed when it returns True, otherwise it remains
            # in the list to be tried again next time.
            if self.functions:
                function = self.functions[0]
                if self.verbose > 2:
                    print("Execute function", function)
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
        """ """

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
        self.encoder.width, self.encoder.height = streams['main']['size']
        self.encoder.format = streams['main']['format']
        self.encoder.stride = streams['main']['stride']
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
                array = np.asarray(array[:, :w*3], order='C')
            image = array.reshape((h, w, 3))
        elif fmt in ("XBGR8888", "XRGB8888"):
            if stride != w * 4:
                array = array.reshape((h, stride))
                array = np.asarray(array[:, :w*4], order='C')
            image = array.reshape((h, w, 4))
        elif fmt[0] == 'S': # raw formats
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
        start_time = time.time()
        img = self.make_image(name)
        if filename.split('.')[-1].lower() in ('jpg', 'jpeg') and img.mode == "RGBA":
            # Nasty hack. Qt doesn't understand RGBX so we have to use RGBA. But saving a JPEG
            # doesn't like RGBA to we have to bodge that to RGBX.
            img.mode = "RGBX"
        # compress_level=1 saves pngs much faster, and still gets most of the compression.
        png_compress_level = self.picam2.options.get("compress_level", 1)
        jpeg_quality = self.picam2.options.get("quality", 90)
        img.save(filename, compress_level=png_compress_level, quality=jpeg_quality)
        if self.picam2.verbose:
            end_time = time.time()
            print("Saved", self, "to file", filename)
            print("Time taken for encode:", (end_time - start_time) * 1000, "ms")


YUV2RGB_JPEG      = np.array([[1.0,   1.0,   1.0  ], [0.0, -0.344, 1.772], [1.402, -0.714, 0.0]])
YUV2RGB_SMPTE170M = np.array([[1.164, 1.164, 1.164], [0.0, -0.392, 2.017], [1.596, -0.813, 0.0]])
YUV2RGB_REC709    = np.array([[1.164, 1.164, 1.164], [0.0, -0.213, 2.112], [1.793, -0.533, 0.0]])

def YUV420_to_RGB(YUV_in, size, matrix=YUV2RGB_JPEG, rb_swap=True, final_width=0):
    """Convert a YUV420 image to an interleaved RGB image of half resolution. The
    size parameter should include padding if there is any, which can be trimmed off
    at the end with the final_width parameter."""
    w, h = size
    w2 = w // 2
    h2 = h // 2
    n = w * h
    n2 = n // 2
    n4 = n // 4

    YUV = np.empty((h2, w2, 3), dtype=int)
    YUV[:,:,0] = YUV_in[:n].reshape(h, w)[0::2,0::2]
    YUV[:,:,1] = YUV_in[n:n + n4].reshape(h2, w2) - 128.0
    YUV[:,:,2] = YUV_in[n + n4:n + n2].reshape(h2, w2) - 128.0

    if rb_swap:
        matrix = matrix[:,[2,1,0]]
    RGB = np.dot(YUV, matrix).clip(0, 255).astype(np.uint8)

    if final_width and final_width != w2:
        RGB = RGB[:,:final_width,:]

    return RGB
