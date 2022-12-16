#!/usr/bin/python3

# Test that we can successfully close a QtGlPreview window and open a new one.

import time

from picamera2 import Picamera2, Preview

preview_type = Preview.NULL

print("First preview...")
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration())
picam2.start_preview(preview_type)
picam2.start()
time.sleep(2)
picam2.close()
print("Done")

print("Second preview...")
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration())
picam2.start_preview(preview_type)
picam2.start()
time.sleep(2)
picam2.close()
print("Done")
