from picamera2 import Picamera2, Preview
from libcamera import Transform
import numpy as np
import time

picam2 = Picamera2()
config = picam2.create_preview_configuration()
picam2.configure(config)
picam2.start_preview(Preview.NULL, transform=Transform(hflip=1, vflip=1))
picam2.start()

overlay = np.zeros((300, 400, 4), dtype=np.uint8)
overlay[:150, 200:] = (255, 0, 0, 64)
overlay[150:, :200] = (0, 255, 0, 64)
overlay[150:, 200:] = (0, 0, 255, 64)

picam2.set_overlay(overlay)
time.sleep(1)
