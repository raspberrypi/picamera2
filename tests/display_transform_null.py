import time

import numpy as np
from libcamera import Transform

from picamera2 import Picamera2, Preview

picam2 = Picamera2()
config = picam2.create_preview_configuration()
picam2.configure(config)
picam2.start_preview(Preview.NULL, transform=Transform(hflip=1, vflip=1))
picam2.start()
time.sleep(1)
picam2.close()
