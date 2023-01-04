#!/usr/bin/python3
# Capture a DNG and a JPEG made from the same raw data.
from picamera2 import Picamera2
from picamera2.configuration import CameraConfig

camera = Picamera2()
camera.start_preview()

preview_config = CameraConfig.for_preview(camera)
camera.configure("preview")

camera.start()
camera.discard_frames(2)

capture_config = CameraConfig.for_still(camera, raw={})
camera.switch_mode(capture_config).result()
request = camera.capture_request(capture_config).result()
request.make_image("main").convert("RGB").save("full.jpg")
request.release()

camera.close()
