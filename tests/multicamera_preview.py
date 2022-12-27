#!/usr/bin/python3

import time

import numpy as np

from picamera2 import Picamera2

camera1 = Picamera2(0)
camera1.configure(camera1.create_preview_configuration())
camera1.start_preview()

camera2 = Picamera2(1)
camera2.configure(camera2.create_preview_configuration())
camera2.start_preview()

camera1.start()
camera2.start()
time.sleep(2)
camera1.stop_preview()
camera2.stop_preview()

time.sleep(2)

camera1.start_preview()
camera2.start_preview()

time.sleep(2)
camera1.close()
camera2.close()
