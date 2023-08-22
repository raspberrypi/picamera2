import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, JpegEncoder, MJPEGEncoder, Quality
from picamera2.outputs import FileOutput

# Not an automatic test really, just something to run to create different
# video files that we can then eyeball for having about the claimed quality.


def do_encode(encoder, quality, filename):
    print(encoder, quality)
    picam2.start_encoder(encoder, output=FileOutput(filename), name='main', quality=quality)
    time.sleep(time_seconds)
    picam2.stop_encoder(encoder)


picam2 = Picamera2()
config = picam2.create_video_configuration({'format': 'BGR888', 'size': (1280, 720)})
picam2.configure(config)
picam2.start()
time_seconds = 5

do_encode(MJPEGEncoder(), Quality.LOW, "mjpeg_low.mjpeg")
do_encode(MJPEGEncoder(), Quality.HIGH, "mjpeg_high.mjpeg")

do_encode(H264Encoder(), Quality.LOW, "h264_low.h264")
do_encode(H264Encoder(), Quality.HIGH, "h264_high.h264")

do_encode(JpegEncoder(), Quality.LOW, "jpeg_low.mjpeg")
do_encode(JpegEncoder(), Quality.HIGH, "jpeg_high.mjpeg")

# play with: ffplay <filename> -vf "setpts=N/30/TB"
