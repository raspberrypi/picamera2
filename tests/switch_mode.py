#!/usr/bin/python3

# Switch from preview to full resolution mode.

import time

from picamera2 import Picamera2

camera = Picamera2()
camera.start_preview()

preview_config = camera.create_preview_configuration()
camera.configure(preview_config)

camera.start()
camera.discard_frames(4)
other_config = camera.create_preview_configuration(
    main={"size": camera.sensor_resolution}, buffer_count=3
)

camera.switch_mode(other_config)
camera.discard_frames(4).result()
camera.stop()
camera.close()
