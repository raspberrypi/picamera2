#!/usr/bin/python3

# Switch from preview to full resolution mode (alternative method).

import time

from picamera2 import Picamera2, Preview

picam2 = Picamera2()
picam2.start_preview(Preview.QTGL)

preview_config = picam2.create_preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(2)
picam2.stop()

size = picam2.sensor_resolution
# GPU won't digest images wider than 4096 on a Pi 4.
if size[0] > 4096:
    height = size[1] * 4096 // size[0]
    height -= height % 2
    size = (4096, height)

other_config = picam2.create_preview_configuration(main={"size": size}, buffer_count=2)
picam2.configure(other_config)

picam2.start()
time.sleep(2)
