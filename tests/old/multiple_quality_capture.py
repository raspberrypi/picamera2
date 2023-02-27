#!/usr/bin/python3
from scicamera import Camera, CameraConfig

camera = Camera()
video_config = CameraConfig.for_video(camera)
camera.configure(video_config)

camera.start()
camera.discard_frames(4).result()
camera.stop()
camera.close()
