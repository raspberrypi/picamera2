#!/usr/bin/python3

# Obtain an image from the camera along with the exact metadata that
# that describes that image.

from picamera2 import Picamera2, Preview
from picamera2.request import PostProcess
import time

picam2 = Picamera2()
post_process = PostProcess(picam2)
picam2.start_preview(Preview.QTGL)

preview_config = picam2.preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(2)

buffers, metadata = picam2.capture_buffers(["main"])
image = post_process.make_image(buffers[0], preview_config["main"])

image.show()
print(metadata)
