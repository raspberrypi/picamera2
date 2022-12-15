import io
import logging
import threading
import time

import numpy as np
import piexif
from pidng.camdefs import Picamera2Camera
from pidng.core import PICAM2DNG
from PIL import Image

import picamera2.formats as formats

from .controls import Controls

_log = logging.getLogger(__name__)


class _MappedBuffer:
    def __init__(self, request, stream):
        stream = request.picam2.stream_map[stream]
        self.__fb = request.request.buffers[stream]

    def __enter__(self):
        import mmap

        # Check if the buffer is contiguous and find the total length.
        fd = self.__fb.planes[0].fd
        planes_metadata = self.__fb.metadata.planes
        buflen = 0
        for p, p_metadata in zip(self.__fb.planes, planes_metadata):
            # bytes_used is the same as p.length for regular frames, but correctly reflects
            # the compressed image size for MJPEG cameras.
            buflen = buflen + p_metadata.bytes_used
            if fd != p.fd:
                raise RuntimeError("_MappedBuffer: Cannot map non-contiguous buffer!")

        self.__mm = mmap.mmap(
            fd, buflen, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE
        )
        return self.__mm

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.__mm is not None:
            self.__mm.close()


class MappedArray:
    def __init__(self, request, stream, reshape=True):
        self.__request = request
        self.__stream = stream
        self.__buffer = _MappedBuffer(request, stream)
        self.__array = None
        self.__reshape = reshape

    def __enter__(self):
        b = self.__buffer.__enter__()
        array = np.array(b, copy=False, dtype=np.uint8)

        if self.__reshape:
            config = self.__request.picam2.camera_config[self.__stream]
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
                    array = array[:, : w * 3]
                array = array.reshape((h, w, 3))
            elif fmt in ("XBGR8888", "XRGB8888"):
                if stride != w * 4:
                    array = array.reshape((h, stride))
                    array = array[:, : w * 4]
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
        self.lock = threading.Lock()
        self.picam2 = picam2
        self.stop_count = picam2.stop_count
        self.configure_count = picam2.configure_count
        self.config = self.picam2.camera_config.copy()

    def acquire(self):
        """Acquire a reference to this completed request, which stops it being recycled back to
        the camera system.
        """
        with self.lock:
            if self.ref_count == 0:
                raise RuntimeError("CompletedRequest: acquiring lock with ref_count 0")
            self.ref_count += 1

    def release(self):
        """Release this completed frame back to the camera system (once its reference count
        reaches zero).
        """
        with self.lock:
            self.ref_count -= 1
            if self.ref_count < 0:
                raise RuntimeError("CompletedRequest: lock now has negative ref_count")
            elif self.ref_count == 0:
                # If the camera has been stopped since this request was returned then we
                # can't recycle it.
                if self.picam2.camera and self.stop_count == self.picam2.stop_count:
                    self.request.reuse()
                    controls = self.picam2.controls.get_libcamera_controls()
                    for id, value in controls.items():
                        self.request.set_control(id, value)
                    self.picam2.controls = Controls(self.picam2)
                    self.picam2.camera.queue_request(self.request)
                self.request = None

    def make_buffer(self, name):
        """Make a 1d numpy array from the named stream's buffer."""
        if self.picam2.stream_map.get(name, None) is None:
            raise RuntimeError(f'Stream "{name}" is not defined')
        with _MappedBuffer(self, name) as b:
            return np.array(b, dtype=np.uint8)

    def get_metadata(self):
        """Fetch the metadata corresponding to this completed request."""
        metadata = {}
        for k, v in self.request.metadata.items():
            metadata[k.name] = self.picam2._convert_from_libcamera_type(v)
        return metadata

    def make_array(self, name):
        """Make a 2d numpy array from the named stream's buffer."""
        return self.picam2.helpers.make_array(self.make_buffer(name), self.config[name])

    def make_image(self, name, width=None, height=None):
        """Make a PIL image from the named stream's buffer."""
        return self.picam2.helpers.make_image(
            self.make_buffer(name), self.config[name], width, height
        )

    def save(self, name, file_output, format=None):
        """Save a JPEG or PNG image of the named stream's buffer."""
        return self.picam2.helpers.save(
            self.make_image(name), self.get_metadata(), file_output, format
        )

    def save_dng(self, filename, name="raw"):
        """Save a DNG RAW image of the raw stream's buffer."""
        return self.picam2.helpers.save_dng(
            self.make_buffer(name), self.get_metadata(), self.config[name], filename
        )


class Helpers:
    """This class implements functionality required by the CompletedRequest methods, but
    in such a way that it can be usefully accessed even without a CompletedRequest object."""

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
                array = np.asarray(array[:, : w * 3], order="C")
            image = array.reshape((h, w, 3))
        elif fmt in ("XBGR8888", "XRGB8888"):
            if stride != w * 4:
                array = array.reshape((h, stride))
                array = np.asarray(array[:, : w * 4], order="C")
            image = array.reshape((h, w, 4))
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
        mode_lookup = {
            "RGB888": "BGR",
            "BGR888": "RGB",
            "XBGR8888": "RGBA",
            "XRGB8888": "BGRX",
        }
        if fmt not in mode_lookup:
            raise RuntimeError(f"Stream format {fmt} not supported for PIL images")
        mode = mode_lookup[fmt]
        pil_img = Image.frombuffer(
            "RGB", (rgb.shape[1], rgb.shape[0]), rgb, "raw", mode, 0, 1
        )
        if width is None:
            width = rgb.shape[1]
        if height is None:
            height = rgb.shape[0]
        if width != rgb.shape[1] or height != rgb.shape[0]:
            # This will be slow. Consider requesting camera images of this size in the first place!
            pil_img = pil_img.resize((width, height))
        return pil_img

    def save(self, img, metadata, file_output, format=None):
        """Save a JPEG or PNG image of the named stream's buffer."""
        # This is probably a hideously expensive way to do a capture.
        start_time = time.monotonic()
        exif = b""
        if isinstance(format, str):
            format_str = format.lower()
        elif isinstance(file_output, str):
            format_str = file_output.split(".")[-1].lower()
        else:
            raise RuntimeError("Cannot detemine format to save")
        if format_str in ("jpg", "jpeg"):
            if img.mode == "RGBA":
                # Nasty hack. Qt doesn't understand RGBX so we have to use RGBA. But saving a JPEG
                # doesn't like RGBA to we have to bodge that to RGBX.
                img.mode = "RGBX"
            # Make up some extra EXIF data.
            if "AnalogueGain" in metadata and "DigitalGain" in metadata:
                zero_ifd = {
                    piexif.ImageIFD.Make: "Raspberry Pi",
                    piexif.ImageIFD.Model: self.picam2.camera.id,
                    piexif.ImageIFD.Software: "Picamera2",
                }
                total_gain = metadata["AnalogueGain"] * metadata["DigitalGain"]
                exif_ifd = {
                    piexif.ExifIFD.ExposureTime: (metadata["ExposureTime"], 1000000),
                    piexif.ExifIFD.ISOSpeedRatings: int(total_gain * 100),
                }
                exif = piexif.dump({"0th": zero_ifd, "Exif": exif_ifd})
        # compress_level=1 saves pngs much faster, and still gets most of the compression.
        png_compress_level = self.picam2.options.get("compress_level", 1)
        jpeg_quality = self.picam2.options.get("quality", 90)
        keywords = {
            "compress_level": png_compress_level,
            "quality": jpeg_quality,
            "format": format,
        }
        if exif != b"":
            keywords |= {"exif": exif}
        img.save(file_output, **keywords)
        end_time = time.monotonic()
        _log.info(f"Saved {self} to file {file_output}.")
        _log.info(f"Time taken for encode: {(end_time-start_time)*1000} ms.")

    def save_dng(self, buffer, metadata, config, filename):
        """Save a DNG RAW image of the raw stream's buffer."""
        start_time = time.monotonic()
        raw = self.make_array(buffer, config)

        camera = Picamera2Camera(config, metadata)
        r = PICAM2DNG(camera)

        dng_compress_level = self.picam2.options.get("compress_level", 0)

        r.options(compress=dng_compress_level)
        r.convert(raw, filename)

        end_time = time.monotonic()
        _log.info(f"Saved {self} to file {filename}.")
        _log.info(f"Time taken for encode: {(end_time-start_time)*1000} ms.")
