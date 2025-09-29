#!/usr/bin/python3

# This shows how to use the remote module to save an image to a file.
# This takes 25 images and save a jpg and a dng for each in a separate process.
# The images are blurred as a simple example of processing the image in a separate process.
# They have the process id that created them in the filename.

import os

import cv2

import picamera2
from picamera2 import Pool, RemoteMappedArray


def init():
    global counter
    counter = 0


def save_image(request):
    global counter
    counter += 1
    with RemoteMappedArray(request, "main") as m:
        temp_image = cv2.medianBlur(m.array, 9)
        m.array[:] = temp_image

    request.save(f"images_{os.getpid()}_{counter}.jpg")
    request.save_dng(f"images_{os.getpid()}_{counter}.dng")


if __name__ == "__main__":
    picam2 = picamera2.Picamera2()
    config = picam2.create_preview_configuration(buffer_count=8)

    with Pool(save_image, 8, picam2, init) as pool:
        # Start the camera after creating the pool so the camera doesn't timeout
        picam2.start(config)
        for _ in range(25):
            with picam2.captured_request() as request:
                pool.send(request)
