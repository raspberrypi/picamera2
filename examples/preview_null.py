#!/usr/bin/python3

import time
from PiCamera2.PiCamera2 import *

picam2 = PiCamera2()
config = picam2.preview_configuration()
picam2.configure(config)

picam2.start_preview(Preview.NULL)

picam2.start()
time.sleep(1)
picam2.stop()
