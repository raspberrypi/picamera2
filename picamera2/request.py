import io
import logging
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import piexif
from pidng.camdefs import Picamera2Camera
from pidng.core import PICAM2DNG
from PIL import Image

import picamera2.formats as formats

from .controls import Controls
from .sensor_format import SensorFormat
from .utils import convert_from_libcamera_type

_log = logging.getLogger(__name__)


class _MappedBuffer:
    def __init__(self, request, stream, write=True):
        if isinstance(stream, str):
            stream = request.stream_map[stream]
        self.__fb = request.request.buffers[stream]
        self.__sync = request.picam2.allocator.sync(request.picam2.allocator, self.__fb, write)

    def __enter__(self):
        self.__mm = self.__sync.__enter__()
        return self.__mm

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.__sync.__exit__(exc_type, exc_value, exc_traceback)


class MappedArray:
    def __init__(self, request, stream, reshape=True, write=True):
        self.__request = request
        self.__stream = stream
        self.__buffer = _MappedBuffer(request, stream, write=write)
        self.__array = None
        self.__reshape = reshape

    def __enter__(self):
        b = self.__buffer.__enter__()
        array = np.array(b, copy=False, dtype=np.uint8)

        if self.__reshape:
            if isinstance(self.__stream, str):
                config = self.__request.config[self.__stream]
                fmt = config["format"]
                w, h = config["size"]
                stride = config["stride"]
            else:
                config = self.__stream.configuration
                fmt = str(config.pixel_format)
                w = config.size.width
                h = config.size.height
                stride = config.stride

            # Turning the 1d array into a 2d image-like array only works if the
            # image stride (which is in bytes) is a whole number of pixels. Even
            # then, if they don't match exactly you will get "padding" down the RHS.
            # Working around this requires another expensive copy of all the data.
            if fmt in ("BGR888", "RGB888"):
                if stride != w * 3:
                    array = array.reshape((h, stride))
                    array = array[:, :w * 3]
                array = array.reshape((h, w, 3))
            elif fmt in ("XBGR8888", "XRGB8888"):
                if stride != w * 4:
                    array = array.reshape((h, stride))
                    array = array[:, :w * 4]
                array = array.reshape((h, w, 4))
            elif fmt in ("YUV420", "YVU420"):
                # Returning YUV420 as an image of 50% greater height (the extra bit continaing
                # the U/V data) is useful because OpenCV can convert it to RGB for us quite
                # efficiently. We leave any packing in there, however, as it would be easier
                # to remove that after conversion to RGB (if that's what the caller does).
                array = array.reshape((h * 3 // 2, stride))
            elif formats.is_raw(fmt):
                array = array.reshape((h, stride))
            else:
                raise RuntimeError("Format " + fmt + " not supported")

        self.__array = array
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.__array is not None:
            del self.__array
        self.__buffer.__exit__(exc_type, exc_value, exc_traceback)

    @property
    def array(self):
        return self.__array


class CompletedRequest:
    def __init__(self, request, picam2):
        self.request = request
        self.ref_count = 1
        self.lock = picam2.request_lock
        self.picam2 = picam2
        self.stop_count = picam2.stop_count
        self.configure_count = picam2.configure_count
        self.config = self.picam2.camera_config.copy()
        self.stream_map = self.picam2.stream_map.copy()
        with self.lock:
            self.syncs = [picam2.allocator.sync(self.picam2.allocator, buffer, False)
                          for buffer in self.request.buffers.values()]
            self.picam2.allocator.acquire(self.request.buffers)
            [sync.__enter__() for sync in self.syncs]

    def acquire(self):
        """Acquire a reference to this completed request, which stops it being recycled back to the camera system."""
        with self.lock:
            if self.ref_count == 0:
                raise RuntimeError("CompletedRequest: acquiring lock with ref_count 0")
            self.ref_count += 1

    def release(self):
        """Release this completed frame back to the camera system (once its reference count reaches zero)."""
        with self.lock:
            self.ref_count -= 1
            if self.ref_count < 0:
                raise RuntimeError("CompletedRequest: lock now has negative ref_count")
            elif self.ref_count == 0:
                # If the camera has been stopped since this request was returned then we
                # can't recycle it.
                if self.picam2.camera and self.stop_count == self.picam2.stop_count and self.picam2.started:
                    self.request.reuse()
                    controls = self.picam2.controls.get_libcamera_controls()
                    for id, value in controls.items():
                        self.request.set_control(id, value)
                    self.picam2.controls = Controls(self.picam2)
                    self.picam2.camera.queue_request(self.request)
                [sync.__exit__() for sync in self.syncs]
                self.picam2.allocator.release(self.request.buffers)
                self.request = None
                self.config = None
                self.stream_map = None

    def make_buffer(self, name):
        """Make a 1d numpy array from the named stream's buffer."""
        if self.stream_map.get(name, None) is None:
            raise RuntimeError(f'Stream {name!r} is not defined')
        with _MappedBuffer(self, name, write=False) as b:
            return np.array(b, dtype=np.uint8)

    def get_metadata(self):
        """Fetch the metadata corresponding to this completed request."""
        metadata = {}
        for k, v in self.request.metadata.items():
            metadata[k.name] = convert_from_libcamera_type(v)
        return metadata

    def make_array(self, name):
        """Make a 2d numpy array from the named stream's buffer."""
        return self.picam2.helpers.make_array(self.make_buffer(name), self.config[name])

    def make_image(self, name, width=None, height=None):
        """Make a PIL image from the named stream's buffer."""
        return self.picam2.helpers.make_image(self.make_buffer(name), self.config[name], width, height)

    def save(self, name, file_output, format=None, exif_data=None):
        """Save a JPEG or PNG image of the named stream's buffer.

        exif_data - dictionary containing user defined exif data (based on `piexif`). This will
            overwrite existing exif information generated by picamera2.
        """
        return self.picam2.helpers.save(self.make_image(name), self.get_metadata(), file_output,
                                        format, exif_data)

    def save_dng(self, file_output, name="raw"):
        """Save a DNG RAW image of the raw stream's buffer."""
        return self.picam2.helpers.save_dng(self.make_buffer(name), self.get_metadata(), self.config[name], file_output)


class Helpers:
    """This class implements functionality required by the CompletedRequest methods.

    In such a way that it can be usefully accessed even without a CompletedRequest object.
    """

    def __init__(self, picam2):
        self.picam2 = picam2

    def make_array(self, buffer, config):
        """Make a 2d numpy array from the named stream's buffer."""
        array = buffer
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
        elif fmt in ("BGR161616", "RGB161616"):
            if stride != w * 6:
                array = array.reshape((h, stride))
                array = np.asarray(array[:, :w * 6], order='C')
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
            image = np.array(Image.open(io.BytesIO(array)))
        elif formats.is_raw(fmt):
            image = array.reshape((h, stride))
        else:
            raise RuntimeError("Format " + fmt + " not supported")
        return image

    def make_image(self, buffer, config, width=None, height=None):
        """Make a PIL image from the named stream's buffer."""
        fmt = config["format"]
        if fmt == "MJPEG":
            return Image.open(io.BytesIO(buffer))
        else:
            rgb = self.make_array(buffer, config)
        mode_lookup = {"RGB888": "BGR", "BGR888": "RGB", "XBGR8888": "RGBX", "XRGB8888": "BGRX"}
        if fmt not in mode_lookup:
            raise RuntimeError(f"Stream format {fmt} not supported for PIL images")
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

    def save(self, img, metadata, file_output, format=None, exif_data=None):
        """Save a JPEG or PNG image of the named stream's buffer.

        exif_data - dictionary containing user defined exif data (based on `piexif`). This will
            overwrite existing exif information generated by picamera2.
        """
        if exif_data is None:
            exif_data = {}
        # This is probably a hideously expensive way to do a capture.
        start_time = time.monotonic()
        exif = b''
        if isinstance(format, str):
            format_str = format.lower()
        elif isinstance(file_output, str):
            format_str = file_output.split('.')[-1].lower()
        elif isinstance(file_output, Path):
            format_str = file_output.suffix.lower()
        else:
            raise RuntimeError("Cannot determine format to save")
        if format_str in ('png') and img.mode == 'RGBX':
            # It seems we can't save an RGBX png file, so make it RGBA instead. We can't use RGBA
            # everywhere, because we can only save an RGBX jpeg, not an RGBA one.
            img = img.convert(mode='RGBA')
        if format_str in ('jpg', 'jpeg'):
            # Make up some extra EXIF data.
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
                exif_dict = exif_dict | exif_data
                exif = piexif.dump(exif_dict)
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

    def save_dng(self, buffer, metadata, config, file_output):
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

        camera = Picamera2Camera(config, metadata)
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

    def decompress(self, array):
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
