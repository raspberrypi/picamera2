#!/usr/bin/python3

# Test that we can successfully close a QtGlPreview window and open a new one.
from scicamera import Camera, CameraConfig

for i in range(2):
    print(f"{i} preview...")
    camera = Camera()
    camera.configure(CameraConfig.for_preview(camera))
    camera.start_preview()
    camera.start()
    camera.discard_frames(5).result()
    camera.close()
    print("Done")
