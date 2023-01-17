#!/usr/bin/python3
from scicamera import Camera, CameraConfig
from scicamera.testing import mature_after_frames_or_timeout

camera = Camera()
fps = 30
dur = 5

micro = int((1 / fps) * 1000000)
video_cfg = CameraConfig.for_video(camera)
video_cfg.controls.FrameDurationLimits = (micro, micro)
camera.configure(video_cfg)

camera.start()
mature_after_frames_or_timeout(camera, 5).result()
camera.stop()
camera.close()
