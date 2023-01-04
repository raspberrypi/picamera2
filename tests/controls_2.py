#!/usr/bin/python3
# Another (simpler!) way to fix the AEC/AGC and AWB.

from picamera2 import CameraConfig, Picamera2

camera = Picamera2()
camera.start_preview()

preview_config = CameraConfig.for_preview(camera)
camera.configure(preview_config)

camera.start()
camera.discard_frames(2)
camera.set_controls({"AwbEnable": 0, "AeEnable": 0})
camera.discard_frames(2).result()
camera.close()
