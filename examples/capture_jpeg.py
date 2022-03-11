#!/usr/bin/python3

# Capture a JPEG while still running in the preview mode. When you
# capture to a file, the return value is the metadata for that image.

from picamera2.picamera2 import *
from picamera2.previews.qt_gl_preview import *
import time

picam2 = Picamera2()

preview_config = picam2.preview_configuration(main={"size": (800, 600)})
picam2.configure(preview_config)

picam2.start_preview(QtGlPreview())

picam2.start_camera()
time.sleep(2)

metadata = picam2.capture_file("test.jpg")
print(metadata)

picam2.close_camera()
