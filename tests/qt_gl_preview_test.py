#!/usr/bin/python3

# Test that we can successfully close a QtGlPreview window and open a new one.

from picamera2.picamera2 import *
import time

preview_type = Preview.QTGL

print("First preview...")
picam2 = Picamera2()
picam2.configure(picam2.preview_configuration())
picam2.start_preview(preview_type)
picam2.start()
time.sleep(2)
picam2.close()
print("Done")

print("Second preview...")
picam2 = Picamera2()
picam2.configure(picam2.preview_configuration())
picam2.start_preview(preview_type)
picam2.start()
time.sleep(2)
picam2.close()
print("Done")
