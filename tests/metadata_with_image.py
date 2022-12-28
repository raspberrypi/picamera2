#!/usr/bin/python3

# Obtain an image from the camera along with the exact metadata that
# that describes that image.
from picamera2 import Picamera2

camera = Picamera2()
camera.start_preview()

preview_config = camera.create_preview_configuration()
camera.configure(preview_config)

camera.start()
camera.discard_frames(2)

request = camera.capture_request().result()
image = request.make_image("main")  # image from the "main" stream
metadata = request.get_metadata()
request.release()  # requests must always be returned to libcamera

image.show()
print(metadata)
camera.close()
