#!/usr/bin/python3

# Capture a DNG and a JPEG made from the same raw data.

from picamera2 import Picamera2, Preview
from picamera2.request import PostProcess
import time

picam2 = Picamera2()
picam2.start_preview(Preview.QTGL)
post_process = PostProcess(picam2)

preview_config = picam2.preview_configuration()
capture_config = picam2.still_configuration(raw={}, display=None)
picam2.configure(preview_config)

picam2.start()
time.sleep(2)

buffers, metadata = picam2.switch_mode_and_capture_buffers(capture_config, ["main", "raw"])
post_process.save(post_process.make_image(buffers[0], capture_config["main"]), metadata, "full.jpg")
post_process.save_dng(buffers[1], metadata, capture_config["raw"], "full.dng")
