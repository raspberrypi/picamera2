#!/usr/bin/python3
# Example of setting controls using the "direct" attribute method.
from scicamera import Camera, CameraConfig
from scicamera.controls import Controls
from scicamera.testing import requires_controls

camera = Camera()


requires_controls(camera, ("ExposureTime", "AnalogueGain"))

camera.start_preview()

preview_config = CameraConfig.for_preview(camera)
camera.configure(preview_config)

camera.start()
camera.discard_frames(2)

controls = Controls(camera)
controls.AnalogueGain = 1.0
controls.ExposureTime = 10000

camera.set_controls(controls)
camera.discard_frames(2).result()
camera.close()
