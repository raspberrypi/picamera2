import time
import threading

from PIL import Image
import libcamera
import numpy as np
import piexif

from pidng.core import PICAM2DNG
from pidng.camdefs import Picamera2Camera


class CompletedRequest:
    def __init__(self, request, picam2):
        self.request = request
        self.ref_count = 1
        self.lock = threading.Lock()
        self.picam2 = picam2
        self.stop_count = picam2.stop_count
        self.configure_count = picam2.configure_count

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
                        self.picam2.camera.queue_request(self.request)
                self.request = None

    def make_buffer(self, name):
        """Make a 1d numpy array from the named stream's buffer."""
        stream = self.picam2.stream_map[name]
        fb = self.request.buffers[stream]
        with libcamera.MappedFrameBuffer(fb) as b:
            return np.array(b.planes[0], dtype=np.uint8)

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
        elif fmt in ("YUV420", "YVU420"):
            # Returning YUV420 as an image of 50% greater height (the extra bit continaing
            # the U/V data) is useful because OpenCV can convert it to RGB for us quite
            # efficiently. We leave any packing in there, however, as it would be easier
            # to remove that after conversion to RGB (if that's what the caller does).
            image = array.reshape((h * 3 // 2, stride))
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

    def save_dng(self, filename, name="raw"):
        """Save a DNG RAW image of the raw stream's buffer."""
        start_time = time.monotonic()
        raw = self.make_array(name)

        fmt = self.picam2.camera_config[name]
        metadata = self.get_metadata()
        camera = Picamera2Camera(fmt, metadata)
        r = PICAM2DNG(camera)

        dng_compress_level = self.picam2.options.get("compress_level", 0)

        r.options(compress=dng_compress_level)
        r.convert(raw, filename)

        end_time = time.monotonic()
        self.picam2.log.info(f"Saved {self} to file {filename}.")
        self.picam2.log.info(f"Time taken for encode: {(end_time-start_time)*1000} ms.")
