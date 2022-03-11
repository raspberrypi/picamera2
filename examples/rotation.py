#!/usr/bin/python3

# Run the camera with a 180 degree rotation.

from picamera2.previews.qt_gl_preview import *
from picamera2.picamera2 import *
import time

picam2 = Picamera2()
picam2.start_preview(QtGlPreview())

preview_config = picam2.preview_configuration()
preview_config["transform"] = libcamera.Transform(hflip=1, vflip=1)
picam2.configure(preview_config)

picam2.start()
time.sleep(5)
