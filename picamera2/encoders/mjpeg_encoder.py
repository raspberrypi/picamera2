"""MJPEG encoder functionality utilising V4L2"""

from v4l2 import V4L2_PIX_FMT_MJPEG

from picamera2.encoders import Quality, _hw_encoder_available
from picamera2.encoders.v4l2_encoder import V4L2Encoder


class MJPEGEncoder(V4L2Encoder):
    """MJPEG encoder utilsing V4L2 functionality"""

    def __init__(self, bitrate=None):
        """Creates MJPEG encoder

        :param bitrate: Bitrate, default None
        :type bitrate: int
        """
        if not _hw_encoder_available:
            raise RuntimeError("Hardware MJPEG not available on this platform")
        super().__init__(bitrate, V4L2_PIX_FMT_MJPEG)

    def _setup(self, quality):
        # If an explicit quality was specified, use it, otherwise try to preserve any bitrate
        # the user may have set for themselves.
        if quality is not None or getattr(self, "bitrate", None) is None:
            quality = Quality.MEDIUM if quality is None else quality
            # These are suggested bitrates for 1080p30 in Mbps
            BITRATE_TABLE = {Quality.VERY_LOW: 16,
                             Quality.LOW: 20,
                             Quality.MEDIUM: 30,
                             Quality.HIGH: 40,
                             Quality.VERY_HIGH: 50}
            reference_complexity = 1920 * 1080 * 30
            actual_complexity = self.width * self.height * getattr(self, "framerate", 30)
            reference_bitrate = BITRATE_TABLE[quality] * 1000000
            self.bitrate = int(reference_bitrate * actual_complexity / reference_complexity)

    def _start(self):
        # The output objects may need to know what kind of stream this is.
        for out in self._output:
            out._add_stream("video", "mjpeg", rate=30)  # seem to need a rate to prevent timestamp warnings

        super()._start()
