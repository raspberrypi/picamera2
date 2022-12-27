#!/usr/bin/python3

# Configure a raw stream and capture an image from it.
import time

from picamera2 import Picamera2

camera = Picamera2()
camera.start_preview()

preview_config = camera.create_preview_configuration(
    raw={"size": camera.sensor_resolution}
)
print(preview_config)
camera.configure(preview_config)

camera.start()
camera.discard_frames(2)
raw = camera.capture_array("raw")
print(raw.shape)
print(camera.stream_configuration("raw"))
