#!/usr/bin/python3

from picamera2 import Picamera2, CameraConfiguration

picam2 = Picamera2()

# We're going to set up some configuration structures, apply each one in
# turn and see if it gave us the configuration we expected.

picam2.preview_configuration.size = (800, 600)
picam2.preview_configuration.format = "RGB888"
picam2.preview_configuration.controls.ExposureTime = 10000

picam2.video_configuration.main.size = (800, 480)
picam2.video_configuration.main.format = "YUV420"
picam2.video_configuration.controls.FrameRate = 25.0

picam2.still_configuration.size = (1024, 768)
picam2.still_configuration.enable_lores()
picam2.still_configuration.lores.format = "YUV420"
picam2.still_configuration.enable_raw()
half_res = tuple([v // 2 for v in picam2.sensor_resolution])
picam2.still_configuration.raw.size = half_res

picam2.configure("preview")
if picam2.controls.ExposureTime != 10000:
    raise RuntimeError("exposure value was not set")
config = CameraConfiguration(picam2.camera_configuration(), picam2)
if config.main.size != (800, 600):
    raise RuntimeError("preview resolution incorrect")

picam2.configure("video")
if picam2.controls.FrameRate < 24.99 or picam2.controls.FrameRate > 25.01:
    raise RuntimeError("framerate was not set")
config = CameraConfiguration(picam2.camera_configuration(), picam2)
if config.size != (800, 480):
    raise RuntimeError("video resolution incorrect")
if config.format != "YUV420":
    raise RuntimeError("video format incorrect")

picam2.configure("still")
config = CameraConfiguration(picam2.camera_configuration(), picam2)
if config.raw.size != half_res:
    raise RuntimeError("still raw size incorrect")
