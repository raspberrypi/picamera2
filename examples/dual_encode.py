import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, MJPEGEncoder
from picamera2.outputs import FileOutput

# Get Picamera2 to encode an H264 stream, and encode another MJPEG one "manually".


picam2 = Picamera2()
config = picam2.create_video_configuration({"size": (1280, 720)}, lores={"size": (640, 360)})
picam2.configure(config)

h264_encoder = H264Encoder()
h264_output = "out.h264"

mjpeg_encoder = MJPEGEncoder()
mjpeg_encoder.framerate = 30
mjpeg_encoder.size = config["lores"]["size"]
mjpeg_encoder.format = config["lores"]["format"]
mjpeg_encoder.bitrate = 5000000
mjpeg_encoder.output = FileOutput("out.mjpeg")
mjpeg_encoder.start()

picam2.start_recording(h264_encoder, h264_output)

start = time.time()
while time.time() - start < 5:
    request = picam2.capture_request()
    mjpeg_encoder.encode("lores", request)
    request.release()

mjpeg_encoder.stop()
picam2.stop_recording()
