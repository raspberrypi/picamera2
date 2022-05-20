import simplejpeg

from picamera2.encoders.multi_encoder import MultiEncoder


class JpegEncoder(MultiEncoder):
    def __init__(self, num_threads=4, q=85, colour_space='RGBX'):
        super().__init__(num_threads=num_threads)
        self.q = q
        self.colour_space = colour_space

    def encode_func(self, request, name):
        array = request.make_array(name)
        return simplejpeg.encode_jpeg(array, quality=self.q, colorspace=self.colour_space)
