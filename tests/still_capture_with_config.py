#!/usr/bin/python3
# Use the configuration structure method to do a full res capture.
from scicamera import Camera

camera = Camera()

# We don't really need to change anyhting, but let's mess around just as a test.
camera.preview_configuration.size = (800, 600)
camera.preview_configuration.format = "YUV420"
camera.still_configuration.size = (1600, 1200)
camera.still_configuration.enable_raw()
camera.still_configuration.raw.size = camera.sensor_resolution

camera.start("preview")
camera.discard_frames(2).result()
assert camera.capture_image(config="still").result()
camera.stop()
camera.close()
