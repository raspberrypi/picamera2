#!/usr/bin/python3

# Obtain an image from the camera along with the exact metadata that
# that describes that image.
from scicamera import Camera, CameraConfig

camera = Camera()
camera.start_preview()

preview_config = CameraConfig.for_preview(camera)
camera.configure(preview_config)

camera.start()
camera.discard_frames(2)

request = camera.capture_request().result()
image = request.make_image("main")  # image from the "main" stream
metadata = request.get_metadata()
request.release()  # requests must always be returned to libcamera

print(metadata)
camera.close()
