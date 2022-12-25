#!/usr/bin/python3

# Test that we can successfully close a QtGlPreview window and open a new one.

import time

from picamera2 import Picamera2

for i in range(2):
    print(f"{i} preview...")
    camera = Picamera2()
    camera.configure(camera.create_preview_configuration())
    camera.start_preview()
    camera.start()
    time.sleep(2)
    camera.close()
    print("Done")
