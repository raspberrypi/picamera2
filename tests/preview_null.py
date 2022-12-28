#!/usr/bin/python3

from picamera2 import Picamera2

camera = Picamera2()
config = camera.create_preview_configuration()
camera.configure(config)

camera.start()
camera.discard_frames(4).result()
camera.stop()
