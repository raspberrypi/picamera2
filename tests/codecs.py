import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, JpegEncoder, MJPEGEncoder
from picamera2.outputs import FileOutput

# Check that all our encoders can be driven "by hand" and "automatically".


def do_encode_by_hand(encoder, stream_name, output_name):
    print("Start encode by hand using", encoder, "to", output_name)
    encoder.output = FileOutput(output_name)
    encoder.start()
    start = time.time()
    while time.time() - start < time_seconds:
        request = picam2.capture_request()
        encoder.encode(stream_name, request)
        request.release()
    encoder.stop()
    print(encoder, "finished!")


def do_encode_auto(encoder, stream_name, output_name):
    print("Start encode by hand using", encoder, "to", output_name)
    picam2.start_encoder(encoder, output=output_name, name=stream_name)
    time.sleep(time_seconds)
    picam2.stop_encoder(encoder)
    print(encoder, "finished!")


picam2 = Picamera2()
config = picam2.create_video_configuration({'format': 'RGB888', 'size': (640, 360)}, lores={'size': (640, 360)})
picam2.configure(config)
picam2.start()
time_seconds = 5

mjpeg_encoder = MJPEGEncoder()
mjpeg_encoder.framerate = 30
mjpeg_encoder.size = config["lores"]["size"]
mjpeg_encoder.format = config["lores"]["format"]
mjpeg_encoder.bitrate = 5000000
do_encode_by_hand(mjpeg_encoder, "lores", "out1.mjpeg")

do_encode_auto(MJPEGEncoder(), "lores", "out1b.mjpeg")

h264_encoder = H264Encoder()
h264_encoder.framerate = 30
h264_encoder.size = config["main"]["size"]
h264_encoder.format = config["main"]["format"]
h264_encoder.bitrate = 5000000
do_encode_by_hand(h264_encoder, "main", "out.h264")

do_encode_auto(H264Encoder(), "lores", "outb.h264")

jpeg_encoder = JpegEncoder()  # needs RGB
jpeg_encoder.size = config["main"]["size"]
jpeg_encoder.format = config["main"]["format"]
jpeg_encoder.q = 50  # wants a quality parameter, not a bitrate (and no framerate)
do_encode_by_hand(jpeg_encoder, "main", "out2.mjpeg")

do_encode_auto(JpegEncoder(), "main", "out2b.mjpeg")
