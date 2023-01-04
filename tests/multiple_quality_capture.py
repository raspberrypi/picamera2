#!/usr/bin/python3
from picamera2 import CameraConfig, Picamera2

camera = Picamera2()
video_config = CameraConfig.for_video(camera)
camera.configure(video_config)

camera.start()
camera.discard_frames(4).result()
camera.stop()
camera.close()
