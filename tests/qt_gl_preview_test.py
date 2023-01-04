#!/usr/bin/python3

# Test that we can successfully close a QtGlPreview window and open a new one.
from picamera2 import CameraConfig, Picamera2

for i in range(2):
    print(f"{i} preview...")
    camera = Picamera2()
    camera.configure(CameraConfig.for_preview(camera))
    camera.start_preview()
    camera.start()
    camera.discard_frames(5).result()
    camera.close()
    print("Done")
