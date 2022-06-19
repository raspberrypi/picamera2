import simplejpeg

from picamera2.encoders.multi_encoder import MultiEncoder
from picamera2.request import PostProcess

class JpegEncoder(MultiEncoder):
    def __init__(self, num_threads=4, q=85, colour_space='RGBX'):
        super().__init__(num_threads=num_threads)
        self.q = q
        self.colour_space = colour_space

    def encode_func(self, request, name):
        post_process = PostProcess(request.picam2)
        array = post_process.make_array(request.make_buffer(name), request.picam2.camera_config[name])
        return simplejpeg.encode_jpeg(array, quality=self.q, colorspace=self.colour_space)
