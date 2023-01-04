from __future__ import annotations

from dataclasses import asdict, dataclass
from logging import getLogger
from typing import TYPE_CHECKING, Any, Optional

import libcamera

from picamera2 import formats
from picamera2.controls import Controls

if TYPE_CHECKING:
    from picamera2.picamera2 import Picamera2

_log = getLogger(__name__)


def _assert_type(thing: Any, type_) -> None:
    if not isinstance(thing, type_):
        raise TypeError(f"{thing} should be a {type_} not {type(thing)}")


@dataclass
class StreamConfiguration:
    size: tuple[int, int]
    format: Optional[str] = None
    stride: Optional[int] = None
    framesize: Optional[int] = None

    @classmethod
    def from_lc_stream_config(cls, libcamera_stream_config):
        return cls(
            format=str(libcamera_stream_config.pixel_format),
            size=(
                libcamera_stream_config.size.width,
                libcamera_stream_config.size.height,
            ),
            stride=libcamera_stream_config.stride,
            framesize=libcamera_stream_config.frame_size,
        )

    def make_dict(self):
        return asdict(self)

    def align(self, optimal=True):
        if optimal:
            # Adjust the image size so that all planes are a mutliple of 32 bytes wide.
            # This matches the hardware behaviour and means we can be more efficient.
            align = 32
            if self.format in ("YUV420", "YVU420"):
                align = 64  # because the UV planes will have half this alignment
            elif self.format in ("XBGR8888", "XRGB8888"):
                align = (
                    16  # 4 channels per pixel gives us an automatic extra factor of 2
                )
        else:
            align = 2
        self.size = (
            self.size[0] - self.size[0] % align,
            self.size[1] - self.size[1] % 2,
        )

    def __post_init__(self) -> None:
        self.check("internal")

    def check(self, name: str):
        """Check the configuration of the passed in config.

        Raises RuntimeError if the configuration is invalid.
        """
        # Check the parameters for a single stream.
        if self.format is not None:
            _assert_type(self.format, str)

            if name == "raw":
                if not formats.is_raw(self.format):
                    raise RuntimeError("Unrecognized raw format " + self.format)
            else:
                if not formats.is_format_valid(self.format):
                    raise RuntimeError(
                        "Bad format " + self.format + " in stream " + name
                    )

        _assert_type(self.size, tuple)
        if len(self.size) != 2:
            raise RuntimeError(
                f"size in {name} stream should be (width, height) got: {self.size}"
            )

        for i in range(2):
            if self.size[i] % 2:
                raise RuntimeError(
                    f"All dimensions in {name} stream should be even got: {self.size}"
                )


@dataclass
class CameraConfiguration:
    camera: Picamera2
    use_case: str
    buffer_count: int
    transform: libcamera._libcamera.Transform
    colour_space: libcamera._libcamera.ColorSpace

    # The are allowed to be a dict when user input, but will
    # be transformed to the proper class by the __post_init__ method.
    controls: Controls | dict
    main: StreamConfiguration | dict
    lores: Optional[StreamConfiguration | dict] = None
    raw: Optional[StreamConfiguration | dict] = None

    # TODO: Remove forward references.
    @property
    def size(self):
        return self.main.size

    @size.setter
    def size(self, value):
        self.main.size = value

    @property
    def format(self):
        return self.main.format

    @format.setter
    def format(self, value):
        self.main.format = value

    def enable_lores(self, enable: bool = True) -> None:
        self.lores = (
            StreamConfiguration(size=self.main.size, format="YUV420")
            if enable
            else None
        )

    def enable_raw(self, enable: bool = True) -> None:
        self.raw = (
            StreamConfiguration(size=self.main.size, format=self.camera.sensor_format)
            if enable
            else None
        )

    def align(self, optimal=True):
        self.main.align(optimal)
        if self.lores is not None:
            self.lores.align(optimal)
        # No sense trying to align the raw stream.

    def get_config(self, config_name: str) -> StreamConfiguration:
        # TODO(meawoppl) - backcompat shim. remove me.
        if config_name == "main":
            return self.main
        if config_name == "lores":
            return self.lores
        if config_name == "raw":
            return self.raw
        raise ValueError("Unknown config name " + config_name)

    def __post_init__(self) -> None:
        if isinstance(self.controls, dict):
            _log.warning("CameraConfiguration controls should be a Controls object")
            self.controls = Controls(self.camera, self.controls)
        if isinstance(self.main, dict):
            _log.warning("CameraConfiguration 'main' should be a StreamConfiguration")
            self.main = StreamConfiguration(**self.main)
        if isinstance(self.lores, dict):
            _log.warning("CameraConfiguration 'lores' should be a StreamConfiguration")
            self.lores = StreamConfiguration(**self.lores)
        if isinstance(self.raw, dict):
            _log.warning("CameraConfiguration 'raw' should be a StreamConfiguration")
            self.raw = StreamConfiguration(**self.raw)

        # Check the entire camera configuration for errors.
        _assert_type(self.colour_space, libcamera._libcamera.ColorSpace)
        _assert_type(self.transform, libcamera._libcamera.Transform)

        self.main.check("main")
        if self.lores is not None:
            self.lores.check("lores")
            main_w, main_h = self.main.size
            lores_w, lores_h = self.lores.size
            if lores_w > main_w or lores_h > main_h:
                raise RuntimeError("lores stream dimensions may not exceed main stream")
            if not formats.is_YUV(self.lores.format):
                raise RuntimeError("lores stream must be YUV")

        if self.raw is not None:
            self.raw.check("raw")
