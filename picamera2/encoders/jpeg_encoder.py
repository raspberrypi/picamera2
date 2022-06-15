"""JPEG encoder functionality"""

import simplejpeg

from picamera2.encoders.multi_encoder import MultiEncoder


class JpegEncoder(MultiEncoder):
    """Uses functionality from MultiEncoder"""

    def __init__(self, num_threads=4, q=85, colour_space='RGBX'):
        """Initialises Jpeg encoder

        :param num_threads: Number of threads to use, defaults to 4
        :type num_threads: int, optional
        :param q: Quality, defaults to 85
        :type q: int, optional
        :param colour_space: Colour space, defaults to 'RGBX'
        :type colour_space: str, optional
        """
        super().__init__(num_threads=num_threads)
        self.q = q
        self.colour_space = colour_space

    def encode_func(self, request, name):
        """Performs encoding

        :param request: Request
        :type request: request
        :param name: Name
        :type name: str
        :return: Jpeg image
        :rtype: bytes
        """
        array = request.make_array(name)
        return simplejpeg.encode_jpeg(array, quality=self.q, colorspace=self.colour_space)
