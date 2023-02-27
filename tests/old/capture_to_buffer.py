#!/usr/bin/python3
import io

from scicamera import Camera, CameraConfig

camera = Camera()
camera.configure(CameraConfig.for_preview(camera))
camera.start()

for i in range(2):
    camera.discard_frames(2)
    data = io.BytesIO()
    camera.capture_file(data, format="jpeg").result()
    print(data.getbuffer().nbytes)
    camera.discard_frames(5)

camera.close()
