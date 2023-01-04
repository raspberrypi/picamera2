#!/usr/bin/python3

# Configure a raw stream and capture an image from it.
from picamera2 import Picamera2

camera = Picamera2()
camera.start_preview()

preview_config = camera.create_preview_configuration(
    raw={"size": camera.sensor_resolution, "format": camera.sensor_format}
)
print(preview_config)

camera.configure(preview_config)
camera.start()
camera.discard_frames(10)
raw = camera.capture_array("raw").result()
print(raw.shape)
print(camera.stream_configuration("raw"))

camera.close()
