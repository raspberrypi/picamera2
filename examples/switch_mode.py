#!/usr/bin/python3

# Switch from preview to full resolution mode.

from PiCamera2.PiCamera2 import *
import time

picam2 = PiCamera2()
picam2.start_preview(Preview.QTGL)

preview_config = picam2.preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(2)

other_config = picam2.preview_configuration(main={"size": picam2.sensor_resolution}, buffer_count=3)

picam2.switch_mode(other_config)
time.sleep(2)
