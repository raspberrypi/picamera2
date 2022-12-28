#!/usr/bin/python3
import numpy as np

from picamera2 import Picamera2

lsize = (320, 240)
camera = Picamera2()
video_config = camera.create_video_configuration(
    main={"size": (1280, 720), "format": "RGB888"},
    lores={"size": lsize, "format": "YUV420"},
)
camera.configure(video_config)
camera.start_preview()
camera.start()

w, h = lsize
prev = None
ltime = 0

for _ in range(4):
    cur = camera.capture_array("lores")
    if prev is not None:
        # Measure pixels differences between current and
        # previous frame
        mse = np.square(np.subtract(cur, prev)).mean()
        print("New Motion", mse)
    prev = cur

camera.close()
