#!/usr/bin/python3
from picamera2 import CameraConfig, Picamera2
from picamera2.testing import mature_after_frames_or_timeout

camera = Picamera2()
video_config = CameraConfig.for_video(camera)
camera.configure(video_config)

camera.start()
mature_after_frames_or_timeout(camera, 5).result()
camera.stop()
