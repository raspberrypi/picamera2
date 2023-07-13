#!/usr/bin/python3
import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, MJPEGEncoder

picam2 = Picamera2()
video_config = picam2.create_video_configuration(main={"size": (1280, 720), "format": "RGB888"},
                                                 lores={"size": (640, 480), "format": "YUV420"})

picam2.configure(video_config)

encoder1 = H264Encoder(10000000)
encoder2 = MJPEGEncoder(10000000)

picam2.start_recording(encoder1, 'test1.h264')
time.sleep(5)
picam2.start_encoder(encoder2, 'test2.mjpeg', name="lores")
time.sleep(5)
picam2.stop_encoder(encoder2)
time.sleep(5)
picam2.stop_recording()
