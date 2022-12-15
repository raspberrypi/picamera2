#!/usr/bin/python3
import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, Quality

picam2 = Picamera2()
video_config = picam2.create_video_configuration()
picam2.configure(video_config)

encoder = H264Encoder()

picam2.start_recording(encoder, "low.h264", quality=Quality.VERY_LOW)
print(encoder._bitrate)
time.sleep(5)
picam2.stop_recording()

picam2.start_recording(encoder, "medium.h264", quality=Quality.MEDIUM)
print(encoder._bitrate)
time.sleep(5)
picam2.stop_recording()

picam2.start_recording(encoder, "high.h264", quality=Quality.VERY_HIGH)
print(encoder._bitrate)
time.sleep(5)
picam2.stop_recording()
