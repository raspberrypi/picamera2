"""JPEG encoder functionality"""

import simplejpeg

from picamera2.encoders import Quality
from picamera2.encoders.multi_encoder import MultiEncoder
from picamera2.request import MappedArray


class JpegEncoder(MultiEncoder):
    """Uses functionality from MultiEncoder"""

    FORMAT_TABLE = {"XBGR8888": "RGBX",
                    "XRGB8888": "BGRX",
                    "BGR888": "RGB",
                    "RGB888": "BGR"}

    def __init__(self, num_threads=4, q=None, colour_space=None, colour_subsampling='420'):
        """Initialises Jpeg encoder

        :param num_threads: Number of threads to use, defaults to 4
        :type num_threads: int, optional
        :param q: Quality, defaults to None
        :type q: int, optional
        :param colour_space: Colour space, defaults to 'RGBX'
        :type colour_space: str, optional
        :param colour_subsampling: Colour subsampling, allows choice of YUV420, YUV422 or YUV444
            outputs. Defaults to '420'.
        :type colour_subsampling: str, optional
        """
        super().__init__(num_threads=num_threads)
        self.q = q
        self.colour_space = colour_space
        self.colour_subsampling = colour_subsampling

    def encode_func(self, request, name):
        """Performs encoding

        :param request: Request
        :type request: request
        :param name: Name
        :type name: str
        :return: Jpeg image
        :rtype: bytes
        """
        fmt = request.config[name]["format"]
        with MappedArray(request, name) as m:
            if fmt == "YUV420":
                width, height = request.config[name]['size']
                Y = m.array[:height, :width]
                reshaped = m.array.reshape((m.array.shape[0] * 2, m.array.strides[0] // 2))
                U = reshaped[2 * height: 2 * height + height // 2, :width // 2]
                V = reshaped[2 * height + height // 2:, :width // 2]
                return simplejpeg.encode_jpeg_yuv_planes(Y, U, V, self.q)
            if self.colour_space is None:
                self.colour_space = self.FORMAT_TABLE[request.config[name]["format"]]
            return simplejpeg.encode_jpeg(m.array, quality=self.q, colorspace=self.colour_space,
                                          colorsubsampling=self.colour_subsampling)

    def _setup(self, quality):
        # If an explicit quality was specified, use it, otherwise try to preserve any q value
        # the user may have set for themselves.
        if quality is not None or getattr(self, "q", None) is None:
            quality = Quality.MEDIUM if quality is None else quality
            # Image size and framerate isn't an issue here, you just get what you get.
            Q_TABLE = {Quality.VERY_LOW: 25,
                       Quality.LOW: 35,
                       Quality.MEDIUM: 50,
                       Quality.HIGH: 65,
                       Quality.VERY_HIGH: 80}
            self.q = Q_TABLE[quality]
