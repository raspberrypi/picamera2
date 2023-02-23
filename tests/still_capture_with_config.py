#!/usr/bin/python3
# Use the configuration structure method to do a full res capture.
from scicamera import Camera
from scicamera.testing import mature_after_frames_or_timeout

camera = Camera()

# We don't really need to change anything, but let's mess around just as a test.
camera.preview_configuration.size = (800, 600)
camera.preview_configuration.format = "YUV420"
camera.still_configuration.size = (1600, 1200)
camera.still_configuration.enable_raw()
camera.still_configuration.raw.size = camera.sensor_resolution

camera.start("preview")
mature_after_frames_or_timeout(camera, 3)
assert camera.capture_image(config="still").result()
camera.stop()
camera.close()
