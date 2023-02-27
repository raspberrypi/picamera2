#!/usr/bin/python3
from scicamera import Camera, CameraConfig
from scicamera.testing import mature_after_frames_or_timeout

camera = Camera()
video_config = CameraConfig.for_video(camera)
camera.configure(video_config)

camera.start()
mature_after_frames_or_timeout(camera, 5).result()
camera.stop()
