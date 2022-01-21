#!/usr/bin/python3

# Switch from preview to full resolution mode (alternative method).

from qt_gl_preview import *
from picamera2 import *
import time

picam2 = Picamera2()
preview = QtGlPreview(picam2)

picam2.open_camera()

preview_config = picam2.preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(2)
picam2.stop()

other_config = picam2.preview_configuration(main={"size": picam2.sensor_resolution}, buffer_count=3)
picam2.configure(other_config)

picam2.start()
time.sleep(2)
