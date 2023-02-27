#!/usr/bin/python3
"""scicamera main classes"""
from __future__ import annotations

import logging
import selectors
import threading
from collections import deque
from dataclasses import dataclass, replace
from functools import partial
from typing import Dict, List

import libcamera

import scicamera.formats as formats
from scicamera.actions import RequestMachinery
from scicamera.configuration import CameraConfig, StreamConfig
from scicamera.controls import Controls
from scicamera.lc_helpers import lc_unpack, lc_unpack_controls
from scicamera.preview import NullPreview
from scicamera.request import CompletedRequest, LoopTask
from scicamera.sensor_format import SensorFormat
from scicamera.tuning import TuningContext

STILL = libcamera.StreamRole.StillCapture
RAW = libcamera.StreamRole.Raw
VIDEO = libcamera.StreamRole.VideoRecording
VIEWFINDER = libcamera.StreamRole.Viewfinder

_log = logging.getLogger(__name__)


# TODO(meawoppl) doc these arrtibutes
@dataclass
class CameraInfo:
    id: str

    model: str

    location: str

    rotation: int

    @staticmethod
    def global_camera_info() -> List[CameraInfo]:
        """
        Return Id string and Model name for all attached cameras, one dict per camera,
        and ordered correctly by camera number. Also return the location and rotation
        of the camera when known, as these may help distinguish which is which.
        """
        infos = []
        for cam in libcamera.CameraManager.singleton().cameras:
            name_to_val = {
                k.name.lower(): v
                for k, v in cam.properties.items()
                if k.name in ("Model", "Location", "Rotation")
            }
            name_to_val["id"] = cam.id
            infos.append(CameraInfo(**name_to_val))
        return infos

    @staticmethod
    def n_cameras() -> int:
        """Return the number of attached cameras."""
        return len(libcamera.CameraManager.singleton().cameras)

    def requires_camera(n: int = 1):
        if CameraInfo.n_cameras() < n:
            _log.error(
                "Camera(s) not found (Do not forget to disable legacy camera with raspi-config)."
            )
            raise RuntimeError(
                "Camera(s) not found (Do not forget to disable legacy camera with raspi-config)."
            )


class CameraManager(RequestMachinery):
    cameras: Dict[int, Camera]

    def __init__(self):
        self.running = False
        self.cameras = {}
        self._lock = threading.Lock()

    def setup(self):
        self.cms = libcamera.CameraManager.singleton()
        self.thread = threading.Thread(target=self.listen, daemon=True)
        self.running = True
        self.thread.start()

    def add(self, index: int, camera: Camera):
        with self._lock:
            self.cameras[index] = camera
            if not self.running:
                self.setup()

    def cleanup(self, index: int):
        flag = False
        with self._lock:
            del self.cameras[index]
            if self.cameras == {}:
                self.running = False
                flag = True
        if flag:
            self.thread.join()
            self.cms = None

    def listen(self):
        sel = selectors.DefaultSelector()
        sel.register(self.cms.event_fd, selectors.EVENT_READ, self.handle_request)

        while self.running:
            events = sel.select(0.2)
            for key, _ in events:
                callback = key.data
                callback()

        sel.unregister(self.cms.event_fd)
        self.cms = None

    def handle_request(self, flushid=None):
        """Handle requests"""
        with self._lock:
            cams = set()
            for req in self.cms.get_ready_requests():
                if (
                    req.status == libcamera.Request.Status.Complete
                    and req.cookie != flushid
                ):
                    cams.add(req.cookie)
                    camera_inst = self.cameras[req.cookie]
                    cleanup_call = partial(
                        camera_inst.recycle_request, camera_inst.stop_count, req
                    )
                    self.cameras[req.cookie].add_completed_request(
                        CompletedRequest(
                            req,
                            replace(camera_inst.camera_config),
                            camera_inst.stream_map,
                            cleanup_call,
                        )
                    )


class Camera(RequestMachinery):
    """Welcome to the Camera class."""

    _cm = CameraManager()

    def __init__(self, camera_num=0, tuning=None):
        """Initialise camera system and open the camera for use.

        :param camera_num: Camera index, defaults to 0
        :type camera_num: int, optional
        :param tuning: Tuning filename, defaults to None
        :type tuning: str, optional
        :raises RuntimeError: Init didn't complete
        """
        super().__init__()

        self._cm.add(camera_num, self)
        self.camera_idx = camera_num
        self._reset_flags()

        with TuningContext(tuning):
            self._open_camera()

        # Configuration requires various bits of information from the camera
        # so we build the default configurations here
        self.preview_configuration = CameraConfig.for_preview(self)
        self.still_configuration = CameraConfig.for_still(self)
        self.video_configuration = CameraConfig.for_video(self)

    @property
    def camera_manager(self):
        return Camera._cm.cms

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
        self.options = {}
        self.post_callback = None
        self.camera_properties_ = {}
        self.controls = Controls(self)
        self.sensor_modes_ = None

    @property
    def preview_configuration(self) -> CameraConfig:
        return self.preview_configuration_

    @preview_configuration.setter
    def preview_configuration(self, value: CameraConfig):
        assert isinstance(value, CameraConfig)
        self.preview_configuration_ = value

    @property
    def still_configuration(self) -> CameraConfig:
        return self.still_configuration_

    @still_configuration.setter
    def still_configuration(self, value: CameraConfig):
        assert isinstance(value, CameraConfig)
        self.still_configuration_ = value

    @property
    def video_configuration(self) -> CameraConfig:
        return self.video_configuration_

    @video_configuration.setter
    def video_configuration(self, value: CameraConfig):
        assert isinstance(value, CameraConfig)
        self.video_configuration_ = value

    @property
    def asynchronous(self) -> bool:
        """True if there is threaded operation

        :return: Thread operation state
        :rtype: bool
        """
        return (
            self._preview is not None
            and getattr(self._preview, "thread", None) is not None
            and self._preview.thread.is_alive()
        )

    @property
    def camera_properties(self) -> dict:
        """Camera properties

        :return: Camera properties
        :rtype: dict
        """
        return {} if self.camera is None else self.camera_properties_

    @property
    def camera_controls(self) -> dict:
        return {
            k: (v[1].min, v[1].max, v[1].default)
            for k, v in self.camera_ctrl_info.items()
        }

    def __enter__(self):
        """Used for allowing use with context manager

        :return: self
        :rtype: Camera
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
        _log.warning(f"__del__ call responsible for cleanup of {self}")
        self.close()

    def _grab_camera(self, idx: str | int):
        if isinstance(idx, str):
            try:
                return self.camera_manager.get(idx)
            except Exception:
                return self.camera_manager.find(idx)
        elif isinstance(idx, int):
            return self.camera_manager.cameras[idx]

    def requires_camera(self):
        if self.camera is None:
            message = "Initialization failed."
            _log.error(message)
            raise RuntimeError(message)

    def _initialize_camera(self) -> None:
        """Initialize camera

        :raises RuntimeError: Failure to initialise camera
        """
        CameraInfo.requires_camera(1)
        self.camera = self._grab_camera(self.camera_idx)
        self.requires_camera()

        self.__identify_camera()
        self.camera_ctrl_info = lc_unpack_controls(self.camera.controls)
        self.camera_properties_ = lc_unpack(self.camera.properties)

        # The next two lines could be placed elsewhere?
        self.sensor_resolution = self.camera_properties_["PixelArraySize"]
        self.sensor_format = str(
            self.camera.generate_configuration([RAW]).at(0).pixel_format
        )

        _log.info("Initialization successful.")

    def __identify_camera(self):
        # TODO(meawoppl) make this a helper on the camera_manager
        for idx, address in enumerate(self.camera_manager.cameras):
            if address == self.camera:
                self.camera_idx = idx
                break

    def _open_camera(self) -> None:
        """Tries to open camera

        :raises RuntimeError: Failed to setup camera
        """
        self._initialize_camera()

        acq_code = self.camera.acquire()
        if acq_code != 0:
            raise RuntimeError(f"camera.acquire() returned unexpected code: {acq_code}")

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
                temp_config = CameraConfig.for_preview(
                    camera=self, raw={"format": str(pix), "size": cam_mode["size"]}
                )
                self.configure(temp_config)
                frameDurationMin = self.camera_controls["FrameDurationLimits"][0]
                cam_mode["fps"] = round(1e6 / frameDurationMin, 2)
                cam_mode["crop_limits"] = self.camera_properties["ScalerCropMaximum"]
                cam_mode["exposure_limits"] = tuple(
                    [i for i in self.camera_controls["ExposureTime"] if i != 0]
                )
                self.sensor_modes_.append(cam_mode)
        return self.sensor_modes_

    # TODO(meawoppl) we don't really support previews, so change the language here
    def start_preview(self) -> None:
        """
        Start the preview loop.
        """
        if self._preview:
            raise RuntimeError("An event loop is already running")

        preview = NullPreview()
        preview.start(self)
        self._preview = preview

    def stop_preview(self) -> None:
        """Stop preview

        :raises RuntimeError: Unable to stop preview
        """
        if not self._preview:
            raise RuntimeError("No preview specified.")

        try:
            self._preview.stop()
            self._preview = None
        except Exception:
            raise RuntimeError("Unable to stop preview.")

    def close(self) -> None:
        """Close camera

        :raises RuntimeError: Closing failed
        """
        if self._preview:
            self.stop_preview()
        if not self.is_open:
            return

        self.stop()
        release_code = self.camera.release()
        if release_code < 0:
            raise RuntimeError(f"Failed to release camera ({release_code})")
        self._cm.cleanup(self.camera_idx)
        self.is_open = False
        self.streams = None
        self.stream_map = None
        self.camera = None
        self.camera_ctrl_info = None
        self.camera_config = None
        self.libcamera_config = None
        self.preview_configuration_ = None
        self.still_configuration_ = None
        self.video_configuration_ = None
        self.allocator = None
        _log.info("Camera closed successfully.")

    # TODO(meawoppl) - Obviated by dataclasses
    @staticmethod
    def _update_libcamera_stream_config(
        libcamera_stream_config, stream_config: StreamConfig, buffer_count: int
    ) -> None:
        # Update the libcamera stream config with ours.
        libcamera_stream_config.size = libcamera.Size(*stream_config.size)
        libcamera_stream_config.pixel_format = libcamera.PixelFormat(
            stream_config.format
        )
        libcamera_stream_config.buffer_count = buffer_count

    # TODO(meawoppl) - Obviated by dataclasses
    def _make_libcamera_config(self, camera_config: CameraConfig):
        # Make a libcamera configuration object from our Python configuration.

        # We will create each stream with the "viewfinder" role just to get the stream
        # configuration objects, and note the positions our named streams will have in
        # libcamera's stream list.
        roles = [VIEWFINDER]
        main_index, lores_index, raw_index = camera_config.get_stream_indices()
        if camera_config.lores is not None:
            roles += [VIEWFINDER]
        if camera_config.raw is not None:
            roles += [RAW]

        # Make the libcamera configuration, and then we'll write all our parameters over
        # the ones it gave us.
        libcamera_config = self.camera.generate_configuration(roles)
        libcamera_config.transform = camera_config.transform
        buffer_count = camera_config.buffer_count
        self._update_libcamera_stream_config(
            libcamera_config.at(main_index), camera_config.main, buffer_count
        )
        libcamera_config.at(main_index).color_space = camera_config.color_space
        if camera_config.lores is not None:
            self._update_libcamera_stream_config(
                libcamera_config.at(lores_index),
                camera_config.lores,
                buffer_count,
            )
            libcamera_config.at(lores_index).color_space = camera_config.color_space

        if camera_config.raw is not None:
            self._update_libcamera_stream_config(
                libcamera_config.at(raw_index), camera_config.raw, buffer_count
            )
            libcamera_config.at(raw_index).color_space = libcamera.ColorSpace.Raw()

        return libcamera_config

    def recycle_request(self, stop_count: int, request: libcamera.Request) -> None:
        """Recycle a request.

        :param request: request
        :type request: libcamera.Request
        """
        if not self.camera:
            _log.warning("Can't recycle request, camera not open")
            return

        if stop_count != self.stop_count:
            _log.warning("Can't recycle request, stop count mismatch")
            return

        request.reuse()
        controls = self.controls.get_libcamera_controls()
        for id, value in controls.items():
            request.set_control(id, value)
        self.controls = Controls(self)
        self.camera.queue_request(request)

    def _make_requests(self) -> List[libcamera.Request]:
        """Make libcamera request objects.

        Makes as many as the number of buffers in the stream with the smallest number of buffers.

        :raises RuntimeError: Failure
        :return: requests
        :rtype: List[libcamera.Request]
        """
        num_requests = min(
            [len(self.allocator.buffers(stream)) for stream in self.streams]
        )
        requests = []
        for i in range(num_requests):
            request = self.camera.create_request(self.camera_idx)
            if request is None:
                raise RuntimeError("Could not create request")

            for stream in self.streams:
                if request.add_buffer(stream, self.allocator.buffers(stream)[i]) < 0:
                    raise RuntimeError("Failed to set request buffer")
            requests.append(request)
        return requests

    def _update_camera_config(
        self, camera_config: CameraConfig, libcamera_config
    ) -> None:
        """Update our camera config from libcamera's.

        :param camera_config: Camera configuration
        :type camera_config: dict
        :param libcamera_config: libcamera configuration
        :type libcamera_config: dict
        """
        _, lores_index, raw_index = camera_config.get_stream_indices()
        camera_config.transform = libcamera_config.transform
        camera_config.color_space = libcamera_config.at(0).color_space
        camera_config.main = StreamConfig.from_lc_stream_config(libcamera_config.at(0))
        if lores_index >= 0:
            camera_config.lores = StreamConfig.from_lc_stream_config(
                libcamera_config.at(lores_index)
            )
        if raw_index >= 0:
            camera_config.raw = StreamConfig.from_lc_stream_config(
                libcamera_config.at(raw_index)
            )

    def _config_opts(self, config: str | dict | CameraConfig) -> CameraConfig:
        if isinstance(config, str):
            config_name_to_camera_config = {
                "preview": self.preview_configuration,
                "still": self.still_configuration,
                "video": self.video_configuration,
            }
            camera_config = config_name_to_camera_config[config]
        elif isinstance(config, dict):
            _log.warning("Using old-style camera config, please update")
            config = config.copy()
            config["camera"] = self
            camera_config = CameraConfig(**config)
        elif isinstance(config, CameraConfig):
            # We expect values to have been set for any lores/raw streams.
            camera_config = config
        else:
            raise RuntimeError(f"Don't know how to make a config from {config}")
        return camera_config

    def _configure(self, config: str | dict | CameraConfig = "preview") -> None:
        """Configure the camera system with the given configuration.

        :param camera_config: Configuration, defaults to the 'preview' configuration
        :type camera_config: dict, string or CameraConfiguration, optional
        :raises RuntimeError: Failed to configure
        """
        if self.started:
            raise RuntimeError("Camera must be stopped before configuring")
        camera_config = self._config_opts(config)

        if camera_config is None:
            camera_config = CameraConfig.for_preview(camera=self)

        # Mark ourselves as unconfigured.
        self.libcamera_config = None
        self.camera_config = None

        # Check the config and turn it into a libcamera config.
        libcamera_config = self._make_libcamera_config(camera_config)

        # Check that libcamera is happy with it.
        status = libcamera_config.validate()
        self._update_camera_config(camera_config, libcamera_config)
        _log.debug(f"Requesting configuration: {camera_config}")
        if status == libcamera.CameraConfiguration.Status.Invalid:
            raise RuntimeError("Invalid camera configuration: {}".format(camera_config))
        elif status == libcamera.CameraConfiguration.Status.Adjusted:
            _log.info("Camera configuration has been adjusted!")

        # Configure libcamera.
        config_call_code = self.camera.configure(libcamera_config)
        if config_call_code:
            raise RuntimeError(
                f"Configuration failed ({config_call_code}): {camera_config}\n{libcamera_config}"
            )
        _log.info("Configuration successful!")
        _log.debug(f"Final configuration: {camera_config}")

        # Update the controls and properties list as some of the values may have changed.
        self.camera_ctrl_info = lc_unpack_controls(self.camera.controls)
        self.camera_properties_ = lc_unpack(self.camera.properties)

        indices = camera_config.get_stream_indices()
        self.stream_map = {}
        for idx, name in zip(indices, ("main", "lores", "raw")):
            if idx >= 0:
                self.stream_map[name] = libcamera_config.at(idx).stream
        # Record which libcamera stream goes with which of our names.
        _log.debug(f"Streams: {self.stream_map}")

        # Allocate all the frame buffers.
        self.streams = [stream_config.stream for stream_config in libcamera_config]

        # TODO(meawoppl) - can be taken off public and used in the 1 function
        # that calls it.
        self.allocator = libcamera.FrameBufferAllocator(self.camera)
        for i, stream in enumerate(self.streams):
            if self.allocator.allocate(stream) < 0:
                _log.critical("Failed to allocate buffers.")
                raise RuntimeError("Failed to allocate buffers.")
            msg = f"Allocated {len(self.allocator.buffers(stream))} buffers for stream {i}."
            _log.debug(msg)
        # Mark ourselves as configured.
        self.libcamera_config = libcamera_config
        self.camera_config = camera_config

        # Set the controls directly so as to overwrite whatever is there.
        self.controls.set_controls(self.camera_config.controls)

    def configure(self, camera_config="preview") -> None:
        """Configure the camera system with the given configuration."""
        self._configure(camera_config)

    def camera_configuration(self) -> CameraConfig:
        """Return the camera configuration."""
        return self.camera_config

    def stream_configuration(self, name="main") -> dict:
        """Return the stream configuration for the named stream."""
        return self.camera_config[name]

    def _start(self) -> None:
        """Start the camera system running."""
        if self.camera_config is None:
            raise RuntimeError("Camera has not been configured")
        if self.started:
            raise RuntimeError("Camera already started")
        controls = self.controls.get_libcamera_controls()
        self.controls = Controls(self)

        return_code = self.camera.start(controls)
        if return_code < 0:
            msg = f"Camera did not start properly. ({return_code})"
            _log.error(msg)
            raise RuntimeError(msg)

        for request in self._make_requests():
            self.camera.queue_request(request)
        self.started = True
        _log.info("Camera started")

    def start(self, config=None) -> None:
        """
        Start the camera system running.

        Camera controls may be sent to the camera before it starts running.

        The following parameters may be supplied:

        config - if not None this is used to configure the camera. This is just a
            convenience so that you don't have to call configure explicitly.
        """
        if self.camera_config is None and config is None:
            config = "preview"
        if config is not None:
            self.configure(config)
        if self.camera_config is None:
            raise RuntimeError("Camera has not been configured")
        # By default we will create an event loop is there isn't one running already.
        if not self._preview:
            self.start_preview()
        self._start()

    def _stop(self) -> None:
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
            self._requests = deque()
            _log.info("Camera stopped")

    def stop(self) -> None:
        """Stop the camera."""
        if not self.started:
            _log.debug("Camera was not started")
            return
        if self.asynchronous:
            self._dispatch_loop_tasks(LoopTask.without_request(self._stop))[0].result()
        else:
            self._stop()

    def set_controls(self, controls) -> None:
        """Set camera controls. These will be delivered with the next request that gets submitted."""
        self.controls.set_controls(controls)
