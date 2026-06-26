#!/usr/bin/python3

# This example shows how to allocate a larger image buffer than you need for
# the camera images, which are then embedded within the larger image.
# Embedding like this only works for the 24 and 32-bit RGB formats.

import time

import numpy as np

from picamera2 import MappedArray, Picamera2, Platform

# VC4 platforms do not support offsets into image buffers.
if Picamera2.platform == Platform.VC4:
    print("SKIPPED (VC4 platform)")
    quit(0)

picam2 = Picamera2()

# Images are 480x360, but we shall embed them in the middle of 640x640 buffers.
picam2.preview_configuration.main.size = (480, 360)
picam2.preview_configuration.main.format = 'XRGB8888'
picam2.preview_configuration.main.buffer = (640, 640)
picam2.preview_configuration.main.offset = (80, 140)

picam2.preview_configuration.enable_lores()
picam2.preview_configuration.lores.size = (480, 360)
picam2.preview_configuration.lores.format = 'RGB888'
picam2.preview_configuration.lores.buffer = (640, 640)
picam2.preview_configuration.lores.offset = (0, 140)

picam2.configure("preview")

picam2.start(show_preview=False)

time.sleep(1)


def check_stream(request, name):
    config = getattr(picam2.preview_configuration, name)

    # Behaviour is unchanged unless we use the "window" parameter.
    with MappedArray(request, name) as m:
        small_image = m.array.copy()

    # Now get a version of this image embedded in the entire image buffer.
    window = (0, 0) + config.buffer
    with MappedArray(request, name, window=window) as m:
        large_image = m.array.copy()

    # Let's check that a crop from the large image matches the smaller image exactly.
    offset = config.offset
    size = config.size
    crop = large_image[offset[1] : offset[1] + size[1], offset[0] : offset[0] + size[0], :]
    if not np.array_equal(crop, small_image):
        print(f"ERROR: small image differs from embedded image in {name} stream")


with picam2.captured_request() as request:
    check_stream(request, 'main')
    check_stream(request, 'lores')
