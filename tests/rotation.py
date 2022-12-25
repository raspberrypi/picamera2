#!/usr/bin/python3

# Run the camera with a 180 degree rotation.
import sys
import time

sys.path.append("/usr/lib/python3/dist-packages")

import libcamera

from picamera2 import Picamera2, Preview

camera = Picamera2()
camera.start_preview(Preview.NULL)

preview_config = camera.create_preview_configuration()
preview_config["transform"] = libcamera.Transform(hflip=1, vflip=1)
camera.configure(preview_config)

camera.start()
time.sleep(2)
