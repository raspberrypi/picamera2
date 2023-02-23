#!/usr/bin/python3
# Start camera with fixed exposure and gain.
from scicamera import Camera, CameraConfig

camera = Camera()
camera.start_preview()

if {"ExposureTime", "AnalogueGain"} < camera.controls.available_control_names():
    controls = {"ExposureTime": 10000, "AnalogueGain": 1.0}
    preview_config = CameraConfig.for_preview(camera, controls=controls)
else:
    preview_config = CameraConfig.for_preview(camera)

camera.configure(preview_config)

camera.start()
camera.discard_frames(2).result()
camera.close()
