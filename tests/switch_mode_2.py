#!/usr/bin/python3

# Switch from preview to full resolution mode (alternative method).

import time

from picamera2 import Picamera2

picam2 = Picamera2()
picam2.start_preview()

preview_config = picam2.create_preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(2)
picam2.stop()

other_config = picam2.create_preview_configuration(
    main={"size": picam2.sensor_resolution}, buffer_count=3
)
picam2.configure(other_config)

picam2.start()
time.sleep(2)
