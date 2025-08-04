from __future__ import annotations

import io
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

import libcamera
import numpy as np
import piexif
import simplejpeg
from pidng.camdefs import Picamera2Camera
from pidng.core import PICAM2DNG
from PIL import Image

import picamera2.formats as formats

from .controls import Controls
from .sensor_format import SensorFormat
from .utils import convert_from_libcamera_type

if TYPE_CHECKING:
    from picamera2.picamera2 import Picamera2

_log = logging.getLogger(__name__)


class _MappedBuffer:
    def __init__(self, request: "CompletedRequest", stream: str, write: bool = True) -> None:
        if isinstance(stream, str):
            stream = request.stream_map[stream]
        assert request.request is not None
        self.__fb = request.request.buffers[stream]
        self.__sync = request.picam2.allocator.sync(request.picam2.allocator, self.__fb, write)

    def __enter__(self) -> Any:
        self.__mm = self.__sync.__enter__()
        return self.__mm

    def __exit__(self, exc_type: Any, exc_value: Any, exc_traceback: Any) -> None:
        self.__sync.__exit__(exc_type, exc_value, exc_traceback)


class MappedArray:
    def __init__(self, request: "CompletedRequest", stream: str, reshape: bool = True, write: bool = True) -> None:
        self.__request: "CompletedRequest" = request
        self.__stream: str = stream
        self.__buffer: _MappedBuffer = _MappedBuffer(request, stream, write=write)
        self.__array: Optional[np.ndarray] = None
        self.__reshape: bool = reshape

    def __enter__(self) -> "MappedArray":
        b = self.__buffer.__enter__()
        array = np.array(b, copy=False, dtype=np.uint8)

        if self.__reshape:
            if isinstance(self.__stream, str):
                config = self.__request.config[self.__stream]
            else:
                config = self.__stream.configuration

            # helpers._make_array_shared never makes a copy.
            array = self.__request.picam2.helpers._make_array_shared(array, config)

        self.__array = array
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, exc_traceback: Any) -> None:
        if self.__array is not None:
            del self.__array
        self.__buffer.__exit__(exc_type, exc_value, exc_traceback)

    @property
    def array(self) -> Optional[np.ndarray]:
        return self.__array


class CompletedRequest:
    FASTER_JPEG = True  # set to False to use the older JPEG encode method

    def __init__(self, request: Any, picam2: "Picamera2") -> None:
        self.request = request
        self.ref_count: int = 1
        self.lock = picam2.request_lock
        self.picam2 = picam2
        self.stop_count: int = picam2.stop_count
        self.configure_count: int = picam2.configure_count
        self.config = self.picam2.camera_config.copy()
        self.stream_map = self.picam2.stream_map.copy()
        with self.lock:
            self.syncs = [picam2.allocator.sync(self.picam2.allocator, buffer, False)
                          for buffer in self.request.buffers.values()]
            self.picam2.allocator.acquire(self.request.buffers)
            [sync.__enter__() for sync in self.syncs]

    def acquire(self) -> None:
        """Acquire a reference to this completed request, which stops it being recycled back to the camera system."""
        with self.lock:
            if self.ref_count == 0:
                raise RuntimeError("CompletedRequest: acquiring lock with ref_count 0")
            self.ref_count += 1

    def release(self) -> None:
        """Release this completed frame back to the camera system (once its reference count reaches zero)."""
        with self.lock:
            self.ref_count -= 1
            if self.ref_count < 0:
                raise RuntimeError("CompletedRequest: lock now has negative ref_count")
            elif self.ref_count == 0:
                # If the camera has been stopped since this request was returned then we
                # can't recycle it.
                if self.picam2.camera and self.stop_count == self.picam2.stop_count and self.picam2.started:
                    assert self.request is not None
                    self.request.reuse()
                    controls = self.picam2.controls.get_libcamera_controls()
                    for id, value in controls.items():

                        # libcamera now has "ExposureTimeMode" and "AnalogueGainMode" which must be set to
                        # manual for the fixed exposure time or gain to have any effect, and cleared to return
                        # to "auto " mode. We're going to hide that by supplying them automatically as needed.
                        if id == libcamera.controls.ExposureTime:
                            if value:
                                self.request.set_control(libcamera.controls.ExposureTimeMode, 1)  # manual
                            else:
                                self.request.set_control(libcamera.controls.ExposureTimeMode, 0)  # auto
                                continue  # no need to set the zero value!
                        elif id == libcamera.controls.AnalogueGain:
                            if value:
                                self.request.set_control(libcamera.controls.AnalogueGainMode, 1)  # manual
                            else:
                                self.request.set_control(libcamera.controls.AnalogueGainMode, 0)  # auto
                                continue  # no need to set the zero value!

                        self.request.set_control(id, value)

                    self.picam2.controls = Controls(self.picam2)
                    self.picam2.camera.queue_request(self.request)
                [sync.__exit__() for sync in self.syncs]
                assert self.request is not None
                self.picam2.allocator.release(self.request.buffers)
                self.request = None
                self.config = {}
                self.stream_map = {}

    def make_buffer(self, name: str) -> np.ndarray:
        """Make a 1D numpy array from the named stream's buffer."""
        if self.stream_map.get(name) is None:
            raise RuntimeError(f'Stream {name!r} is not defined')
        with _MappedBuffer(self, name, write=False) as b:
            return np.array(b, dtype=np.uint8)

    def get_metadata(self) -> Dict[str, Any]:
        """Fetch the metadata corresponding to this completed request."""
        metadata = {}
        assert self.request is not None
        for k, v in self.request.metadata.items():
            metadata[k.name] = convert_from_libcamera_type(v)
        return metadata

    def make_array(self, name: str) -> np.ndarray:
        """Make a 2d numpy array from the named stream's buffer."""
        config = self.config.get(name, None)
        if config is None:
            raise RuntimeError(f'Stream {name!r} is not defined')
        elif config['format'] == 'MJPEG':
            return np.array(Image.open(io.BytesIO(self.make_buffer(name))))

        # We don't want to send out an exported handle to the camera buffer, so we're going to have
        # to do a copy. If the buffer is not contiguous, we can use the copy to make it so.
        with MappedArray(self, name) as m:
            if m.array.data.c_contiguous:
                return np.copy(m.array)
            else:
                return np.ascontiguousarray(m.array)

    def make_image(self, name: str, width: Optional[int] = None, height: Optional[int] = None) -> Image.Image:
        """Make a PIL image from the named stream's buffer."""
        config = self.config.get(name, None)
        if config is None:
            raise RuntimeError(f'Stream {name!r} is not defined')

        fmt = config['format']
        if fmt == 'MJPEG':
            return Image.open(io.BytesIO(self.make_buffer(name)))
        mode = self.picam2.helpers._get_pil_mode(fmt)

        with MappedArray(self, name, write=False) as m:
            shape = m.array.shape
            # At this point, array is the same memory as the camera buffer - no copy has happened.
            buffer = m.array
            stride = m.array.strides[0]
            if mode == "RGBX":
                # FOr RGBX mode only, PIL shares the underlying buffer. So if we don't want to pass
                # out a handle to the camera buffer, then we must copy it.
                buffer = np.copy(m.array)
                stride = buffer.strides[0]
            elif not m.array.data.c_contiguous:
                # PIL will accept images with padding, but we must give it a contiguous buffer and
                # pass the stride as the penultimate "magic" parameter to frombuffer.
                buffer = m.array.base

            pil_img = Image.frombuffer("RGB", (shape[1], shape[0]), buffer, "raw", mode, stride, 1)

        width = width or shape[1]
        height = height or shape[0]
        if width != shape[1] or height != shape[0]:
            # This will be slow. Consider requesting camera images of this size in the first place!
            pil_img = pil_img.resize((width, height))
        return pil_img

    def save(self, name: str, file_output: Any, format: Optional[str] = None,
             exif_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Save a JPEG or PNG image of the named stream's buffer.

        exif_data - dictionary containing user defined exif data (based on `piexif`). This will
            overwrite existing exif information generated by picamera2.
        """
        # We have a more optimised path for writing JPEGs using simplejpeg.
        config = self.config.get(name, None)
        if config is None:
            raise RuntimeError(f'Stream {name!r} is not defined')
        if (config['format'] == 'YUV420' or (self.FASTER_JPEG and config['format'] != "MJPEG")) and \
           self.picam2.helpers._get_format_str(file_output, format) in ('jpg', 'jpeg'):
            quality = self.picam2.options.get("quality", 90)
            with MappedArray(self, name) as m:
                format = self.config[name]["format"]
                if format == 'YUV420':
                    width, height = self.config[name]['size']
                    Y = m.array[:height, :width]
                    reshaped = m.array.reshape((m.array.shape[0] * 2, m.array.strides[0] // 2))
                    U = reshaped[2 * height: 2 * height + height // 2, :width // 2]
                    V = reshaped[2 * height + height // 2:, :width // 2]
                    output_bytes = simplejpeg.encode_jpeg_yuv_planes(Y, U, V, quality)
                    Y = reshaped = U = V = None
                else:
                    FORMAT_TABLE = {"XBGR8888": "RGBX", "XRGB8888": "BGRX", "BGR888": "RGB", "RGB888": "BGR"}
                    output_bytes = simplejpeg.encode_jpeg(m.array, quality, FORMAT_TABLE[format], '420')

            exif = self.picam2.helpers._prepare_exif(self.get_metadata(), exif_data)

            if isinstance(file_output, io.BytesIO):
                f = file_output
            else:
                f = open(file_output, 'wb')
            try:
                if exif:
                    # Splice in the exif data as we write it out.
                    f.write(output_bytes[:2] + bytes.fromhex('ffe1') + (len(exif) + 2).to_bytes(2, 'big'))
                    f.write(exif)
                    f.write(output_bytes[2:])
                else:
                    f.write(output_bytes)
            except Exception:
                if f is not file_output:
                    f.close()
        else:
            return self.picam2.helpers.save(self.make_image(name), self.get_metadata(), file_output,
                                            format, exif_data)

    def save_dng(self, file_output: Any, name: str = "raw") -> None:
        """Save a DNG RAW image of the raw stream's buffer."""
        # Don't use make_buffer(), this saves a copy.
        if self.stream_map.get(name) is None:
            raise RuntimeError(f'Stream {name!r} is not defined')
        with _MappedBuffer(self, name, write=False) as b:
            buffer = np.array(b, copy=False, dtype=np.uint8)
            return self.picam2.helpers.save_dng(buffer, self.get_metadata(), self.config[name], file_output)


class Helpers:
    """This class implements functionality required by the CompletedRequest methods.

    In such a way that it can be usefully accessed even without a CompletedRequest object.
    """

    def __init__(self, picam2: "Picamera2"):
        self.picam2 = picam2

    def _make_array_shared(self, buffer: np.ndarray, config: Dict[str, Any]) -> np.ndarray:
        """Makes a 2d numpy array from the named stream's buffer without copying memory.

        This method makes an array that is guaranteed to be shared with the underlying
        buffer, that is, no copy of the pixel data is made.
        """
        array = buffer
        fmt = config["format"]
        w, h = config["size"]
        stride = config["stride"]

        # Reshape the 1d array into an image, and "slice" off any padding bytes on the
        # right hand edge (which doesn't copy the pixel data).
        if fmt in ("BGR888", "RGB888"):
            if stride != w * 3:
                array = array.reshape((h, stride))
                array = array[:, :w * 3]
            image = array.reshape((h, w, 3))
        elif fmt in ("XBGR8888", "XRGB8888"):
            if stride != w * 4:
                array = array.reshape((h, stride))
                array = array[:, :w * 4]
            image = array.reshape((h, w, 4))
        elif fmt in ("BGR161616", "RGB161616"):
            if stride != w * 6:
                array = array.reshape((h, stride))
                array = array[:, :w * 6]
            array = array.view(np.uint16)
            image = array.reshape((h, w, 3))
        elif fmt in ("YUV420", "YVU420"):
            # Returning YUV420 as an image of 50% greater height (the extra bit continaing
            # the U/V data) is useful because OpenCV can convert it to RGB for us quite
            # efficiently. We leave any packing in there, however, as it would be easier
            # to remove that after conversion to RGB (if that's what the caller does).
            image = array.reshape((h * 3 // 2, stride))
        elif fmt in ("YUYV", "YVYU", "UYVY", "VYUY"):
            # These dimensions seem a bit strange, but mean that
            # cv2.cvtColor(image, cv2.COLOR_YUV2BGR_YUYV) will convert directly to RGB.
            image = array.reshape(h, stride // 2, 2)
        elif fmt == "MJPEG":
            image = np.array(Image.open(io.BytesIO(array)))  # type: ignore
        elif formats.is_raw(fmt):
            image = array.reshape((h, stride))
        else:
            raise RuntimeError("Format " + fmt + " not supported")
        return image

    def make_array(self, buffer, config):
        """Makes a 2d numpy array for the named stream's buffer.

        This method makes a copy of the underlying camera buffer, so that it can be
        safely returned to the camera system.
        """
        array = self._make_array_shared(buffer, config)
        if array.data.c_contiguous:
            return np.copy(array)
        else:
            return np.ascontiguousarray(array)

    def _get_pil_mode(self, fmt):
        mode_lookup = {"RGB888": "BGR", "BGR888": "RGB", "XBGR8888": "RGBX", "XRGB8888": "BGRX"}
        mode = mode_lookup.get(fmt, None)
        if mode is None:
            raise RuntimeError(f"Stream format {fmt} not supported for PIL images")
        return mode

    def make_image(self, buffer: np.ndarray, config: Dict[str, Any], width: Optional[int] = None,
                   height: Optional[int] = None) -> Image.Image:
        """Make a PIL image from the named stream's buffer."""
        fmt = config["format"]
        if fmt == "MJPEG":
            return Image.open(io.BytesIO(buffer))  # type: ignore
        else:
            rgb = self._make_array_shared(buffer, config)

        # buffer was already a copy, so don't need to worry about an extra copy for the "RGBX" mode.
        buf = rgb
        if not rgb.data.c_contiguous:
            buf = rgb.base

        mode = self._get_pil_mode(fmt)
        pil_img = Image.frombuffer("RGB", (rgb.shape[1], rgb.shape[0]), buf, "raw", mode, rgb.strides[0], 1)

        width = width or rgb.shape[1]
        height = height or rgb.shape[0]
        if width != rgb.shape[1] or height != rgb.shape[0]:
            # This will be slow. Consider requesting camera images of this size in the first place!
            pil_img = pil_img.resize((width, height))  # type: ignore
        return pil_img

    def _prepare_exif(self, metadata, exif_data):
        exif = b''
        if "AnalogueGain" in metadata and "DigitalGain" in metadata:
            datetime_now = datetime.now().strftime("%Y:%m:%d %H:%M:%S")
            zero_ifd = {piexif.ImageIFD.Make: "Raspberry Pi",
                        piexif.ImageIFD.Model: self.picam2.camera.id,
                        piexif.ImageIFD.Software: "Picamera2",
                        piexif.ImageIFD.DateTime: datetime_now}
            total_gain = metadata["AnalogueGain"] * metadata["DigitalGain"]
            exif_ifd = {piexif.ExifIFD.DateTimeOriginal: datetime_now,
                        piexif.ExifIFD.ExposureTime: (metadata["ExposureTime"], 1000000),
                        piexif.ExifIFD.ISOSpeedRatings: int(total_gain * 100)}
            exif_dict = {"0th": zero_ifd, "Exif": exif_ifd}
            # merge user provided exif data, overwriting the defaults
            exif_dict = exif_dict | (exif_data or {})
            exif = piexif.dump(exif_dict)
        return exif

    def _get_format_str(self, file_output, format):
        if isinstance(format, str):
            return format.lower()
        elif isinstance(file_output, str):
            return file_output.split('.')[-1].lower()
        elif isinstance(file_output, Path):
            return file_output.suffix.lower()
        else:
            raise RuntimeError("Cannot determine format to save")

    def save(self, img: Image.Image, metadata: Dict[str, Any], file_output: Union[str, Path], format: Optional[str] = None,
             exif_data: Optional[Dict] = None) -> None:
        """Save a JPEG or PNG image of the named stream's buffer.

        exif_data - dictionary containing user defined exif data (based on `piexif`). This will
            overwrite existing exif information generated by picamera2.
        """
        if exif_data is None:
            exif_data = {}
        # This is probably a hideously expensive way to do a capture.
        start_time = time.monotonic()
        format_str = self._get_format_str(file_output, format)
        if format_str in ('png') and img.mode == 'RGBX':
            # It seems we can't save an RGBX png file, so make it RGBA instead. We can't use RGBA
            # everywhere, because we can only save an RGBX jpeg, not an RGBA one.
            img = img.convert(mode='RGBA')
        exif = b''
        if format_str in ('jpg', 'jpeg'):
            # Make up some extra EXIF data.
            exif = self._prepare_exif(metadata, exif_data)
        # compress_level=1 saves pngs much faster, and still gets most of the compression.
        png_compress_level = self.picam2.options.get("compress_level", 1)
        jpeg_quality = self.picam2.options.get("quality", 90)
        keywords = {"compress_level": png_compress_level, "quality": jpeg_quality, "format": format}
        if exif != b'':
            keywords |= {"exif": exif}
        img.save(file_output, **keywords)
        end_time = time.monotonic()
        _log.info(f"Saved {self} to file {file_output}.")
        _log.info(f"Time taken for encode: {(end_time-start_time)*1000} ms.")

    def save_dng(self, buffer: np.ndarray, metadata: Dict[str, Any], config: Dict[str, Any], file_output: Any) -> None:
        """Save a DNG RAW image of the raw stream's buffer."""
        start_time = time.monotonic()
        raw = self.make_array(buffer, config)
        config = config.copy()

        fmt = SensorFormat(config['format'])
        if fmt.packing == 'PISP_COMP1':
            raw = self.decompress(raw)
            fmt.bit_depth = 16
            config['format'] = fmt.unpacked
            config['stride'] = raw.shape[1]
            config['framesize'] = raw.shape[0] * raw.shape[1]

        model = self.picam2.camera_properties.get('Model') or "Picamera2"
        camera = Picamera2Camera(config, metadata, model)
        r = PICAM2DNG(camera)

        dng_compress_level = self.picam2.options.get("compress_level", 0)

        r.options(compress=dng_compress_level)
        # PiDNG doesn't accpet a BytesIO, but returns a byte array if the filename is empty.
        if isinstance(file_output, io.BytesIO):
            buf = r.convert(raw, "")
            file_output.write(buf)
        else:
            r.convert(raw, str(file_output))

        end_time = time.monotonic()
        _log.info(f"Saved {self} to file {file_output}.")
        _log.info(f"Time taken for encode: {(end_time-start_time)*1000} ms.")

    def decompress(self, array: np.ndarray):
        """Decompress an image buffer that has been compressed with a PiSP compression format."""
        # These are the standard configurations used in the drivers.
        offset = 2048

        words = array.view(np.int32)  # Assume all Pis are little-endian. Note signed arithmetic is used!
        words = words.reshape((words.shape[0], words.shape[1] // 2, 2))  # pairs of words by component
        qmode = words & 3
        pix0 = (words >> 2) & 511
        pix1 = ((words >> 11) & 127) - 64
        pix2 = (words >> 18) & 127
        pix3 = (words >> 25) & 127
        q1 = np.copy(pix0)
        q2 = pix1 + 448
        np.maximum(pix0, pix0 - pix1, where=(qmode * pix0 < 768), out=q1)
        np.maximum(pix0, pix0 + pix1, where=(qmode * pix0 < 768), out=q2)
        q0 = np.minimum(1536 >> qmode, np.maximum(0, q1 - 64)) + pix2
        q3 = np.minimum(1536 >> qmode, np.maximum(0, q2 - 64)) + pix3
        np.maximum(np.maximum(16 * q0, 32 * (q0 - 160)), 64 * qmode * q0, out=pix0)
        np.maximum(np.maximum(16 * q1, 32 * (q1 - 160)), 64 * qmode * q1, out=pix1)
        np.maximum(np.maximum(16 * q2, 32 * (q2 - 160)), 64 * qmode * q2, out=pix2)
        np.maximum(np.maximum(16 * q3, 32 * (q3 - 160)), 64 * qmode * q3, out=pix3)
        q2 = (words >> 2) & 32767
        q3 = (words >> 17) & 32767
        q0 = (q2 & 15) + 16 * ((q2 >> 8) // 11)
        q1 = (q2 >> 4) % 176
        q2 = (q3 & 15) + 16 * ((q3 >> 8) // 11)
        q3 = (q3 >> 4) % 176
        np.maximum(256 * q0, 512 * (q0 - 47), out=pix0, where=(qmode == 3))
        np.maximum(256 * q1, 512 * (q1 - 47), out=pix1, where=(qmode == 3))
        np.maximum(256 * q2, 512 * (q2 - 47), out=pix2, where=(qmode == 3))
        np.maximum(256 * q3, 512 * (q3 - 47), out=pix3, where=(qmode == 3))
        res = np.stack((pix0, pix1, pix2, pix3), axis=2).reshape(array.shape)

        res = np.clip(res + offset, 0, 65535).astype(np.uint16)
        return res.view(np.uint8)
