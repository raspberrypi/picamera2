#!/usr/bin/python3

# Test that we can successfully close a QtGlPreview window and open a new one.

from PiCamera2.PiCamera2 import *
import time

preview_type = Preview.DRM

print("First preview...")
picam2 = PiCamera2()
picam2.configure(picam2.preview_configuration())
picam2.start_preview(preview_type)
picam2.start()
time.sleep(2)
picam2.close()
print("Done")

print("Second preview...")
picam2 = PiCamera2()
picam2.configure(picam2.preview_configuration())
picam2.start_preview(preview_type)
picam2.start()
time.sleep(2)
picam2.close()
print("Done")
