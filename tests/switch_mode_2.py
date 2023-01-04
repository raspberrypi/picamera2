#!/usr/bin/python3

# Switch from preview to full resolution mode (alternative method).
from picamera2 import CameraConfig, Picamera2

camera = Picamera2()
camera.start_preview()

preview_config = CameraConfig.for_preview(camera)
camera.configure(preview_config)

camera.start()
camera.discard_frames(4)
camera.stop()

other_config = CameraConfig.for_preview(
    camera, main={"size": camera.sensor_resolution}, buffer_count=3
)
camera.configure(other_config)

camera.start()
camera.discard_frames(4).result()
camera.stop()
camera.close()
