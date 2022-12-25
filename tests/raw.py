#!/usr/bin/python3

# Configure a raw stream and capture an image from it.
import time

from picamera2 import Picamera2, Preview

camera = Picamera2()
camera.start_preview(Preview.NULL)

preview_config = camera.create_preview_configuration(
    raw={"size": camera.sensor_resolution}
)
print(preview_config)
camera.configure(preview_config)

camera.start()
time.sleep(2)

raw = camera.capture_array("raw")
print(raw.shape)
print(camera.stream_configuration("raw"))
