#!/usr/bin/python3
import time
from unittest.mock import MagicMock

from picamera2 import Picamera2

camera = Picamera2()
fps = 30
dur = 5

micro = int((1 / fps) * 1000000)
video_cfg = camera.create_video_configuration()
video_cfg["controls"]["FrameDurationLimits"] = (micro, micro)

camera.configure(video_cfg)

mock = MagicMock()
camera.add_request_callback(lambda r: mock())

camera.start()
for i in range(50):
    if mock.call_count >= 5:
        break
    time.sleep(0.1)

camera.close()

assert mock.call_count > 0
