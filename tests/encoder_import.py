from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.platform import Platform

encoder = H264Encoder(bitrate=1000000)
encoder_name = encoder.__class__.__name__
platform = Picamera2.platform

if platform == Platform.VC4:
    error = encoder_name != "H264Encoder"
elif platform == Platform.PISP:
    error = encoder_name != "LibavH264Encoder"

if error:
    print("ERROR: Unexpected encoder, got", encoder_name, "for platform", platform)
