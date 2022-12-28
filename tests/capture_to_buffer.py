#!/usr/bin/python3
import io

from picamera2 import Picamera2

camera = Picamera2()
capture_config = camera.create_still_configuration()
camera.configure(camera.create_preview_configuration())
camera.start()

for i in range(2):
    camera.discard_frames(2)
    data = io.BytesIO()
    camera.capture_file(data, format="jpeg").result()
    print(data.getbuffer().nbytes)
    camera.discard_frames(5)

camera.close()
