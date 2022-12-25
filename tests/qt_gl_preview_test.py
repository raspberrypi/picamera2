#!/usr/bin/python3

# Test that we can successfully close a QtGlPreview window and open a new one.

import time

from picamera2 import Picamera2, Preview

preview_type = Preview.NULL

print("First preview...")
camera = Picamera2()
camera.configure(camera.create_preview_configuration())
camera.start_preview(preview_type)
camera.start()
time.sleep(2)
camera.close()
print("Done")

print("Second preview...")
camera = Picamera2()
camera.configure(camera.create_preview_configuration())
camera.start_preview(preview_type)
camera.start()
time.sleep(2)
camera.close()
print("Done")
