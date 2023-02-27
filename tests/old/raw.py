#!/usr/bin/python3

# Configure a raw stream and capture an image from it.
from scicamera import Camera, CameraConfig

camera = Camera()
camera.start_preview()

preview_config = CameraConfig.for_preview(
    camera, raw={"size": camera.sensor_resolution, "format": camera.sensor_format}
)
print(preview_config)

camera.configure(preview_config)
camera.start()
camera.discard_frames(10)
raw = camera.capture_array("raw").result()
print(raw.shape)
print(camera.stream_configuration("raw"))

camera.close()
