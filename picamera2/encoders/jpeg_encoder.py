"""JPEG encoder functionality"""
from io import BytesIO

from PIL.Image import Image

from picamera2.encoders import Quality
from picamera2.encoders.multi_encoder import MultiEncoder


class JpegEncoder(MultiEncoder):
    """Uses functionality from MultiEncoder"""

    def __init__(
        self, num_threads=4, q=None, colour_space="RGBX", colour_subsampling="420"
    ):
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
        self.requested_q = q
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
        img: Image = request.make_image(name)
        bio = BytesIO()
        img.save(bio, format="jpeg", quality=self.q)
        return bio.getvalue()

    def _setup(self, quality):
        if self.requested_q is None:
            # Image size and framerate isn't an issue here, you just get what you get.
            Q_TABLE = {
                Quality.VERY_LOW: 20,
                Quality.LOW: 40,
                Quality.MEDIUM: 60,
                Quality.HIGH: 75,
                Quality.VERY_HIGH: 90,
            }
            self.q = Q_TABLE[quality]
        else:
            self.q = self.requested_q
