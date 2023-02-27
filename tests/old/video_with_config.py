#!/usr/bin/python3

# Use the configuration structure method to do a full res capture.
from scicamera import Camera

camera = Camera()

# We don't really need to change anything, but let's mess around just as a test.
camera.video_configuration.size = (800, 480)
camera.video_configuration.format = "YUV420"

camera.start()
camera.discard_frames(2).result()
camera.stop()
