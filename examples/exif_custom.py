#!/usr/bin/python3

import io

import piexif
import PIL.Image

from picamera2 import Picamera2

# We'll save a jpeg to memory with some custom exif in it...
mem = io.BytesIO()
my_name = "My Random Camera"
custom_exif = {'0th': {piexif.ImageIFD.Model: my_name}}

with Picamera2() as picam2:
    picam2.start()
    picam2.capture_file(mem, format='jpeg', exif_data=custom_exif)

# And read it back to check it was there!
exif_check = piexif.load(PIL.Image.open(mem).info['exif'])
my_name_check = exif_check['0th'][piexif.ImageIFD.Model]

if my_name_check.decode('ascii') != my_name:
    print("ERROR: custom exif data was not respected")
