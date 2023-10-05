import io
import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, JpegEncoder, MJPEGEncoder, Quality
from picamera2.outputs import FileOutput

# Check that low quality streams come out smaller than high quality ones! This is of
# course dependent on the images returned by the camera, but hopefully the difference
# between very low/high is so great that the behaviour should be reliable enough.


def do_encode(encoder, quality):
    data = io.BytesIO()
    picam2.start_encoder(encoder, output=FileOutput(data), name='main', quality=quality)
    time.sleep(time_seconds)
    picam2.stop_encoder(encoder)
    return data.getbuffer().nbytes


picam2 = Picamera2()
config = picam2.create_video_configuration({'format': 'RGB888', 'size': (640, 360)}, lores={'size': (640, 360)})
picam2.configure(config)
picam2.start()
time_seconds = 5

low_quality = do_encode(MJPEGEncoder(), Quality.VERY_LOW)
high_quality = do_encode(MJPEGEncoder(), Quality.VERY_HIGH)
print("MJPEGEncoder: low quality", low_quality, "high quality", high_quality)
if (low_quality > high_quality):
    print("Error: MJPEGEncoder file sizes not as expected")

low_quality = do_encode(H264Encoder(), Quality.VERY_LOW)
high_quality = do_encode(H264Encoder(), Quality.VERY_HIGH)
print("H264Encoder: low quality", low_quality, "high quality", high_quality)
if (low_quality > high_quality):
    print("Error: H264Encoder file sizes not as expected")

low_quality = do_encode(JpegEncoder(), Quality.VERY_LOW)
high_quality = do_encode(JpegEncoder(), Quality.VERY_HIGH)
print("JpegEncoder: low quality", low_quality, "high quality", high_quality)
if (low_quality > high_quality):
    print("Error: JpegEncoder file sizes not as expected")
