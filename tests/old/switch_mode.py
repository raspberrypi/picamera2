#!/usr/bin/python3

# Switch from preview to full resolution mode.

from scicamera import Camera, CameraConfig

camera = Camera()
camera.start_preview()

preview_config = CameraConfig.for_preview(camera)
camera.configure(preview_config)

camera.start()
camera.discard_frames(4)
other_config = CameraConfig.for_preview(
    camera, main={"size": camera.sensor_resolution}, buffer_count=3
)

camera.switch_mode(other_config)
camera.discard_frames(4).result()
camera.stop()
camera.close()
