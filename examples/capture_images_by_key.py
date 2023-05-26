#!/usr/bin/python3

# Capture a PNG image while still running in the preview mode.
# The image release is activated with the button 'p' and with 'q' the script is stopped.

from picamera2 import Picamera2, Preview

from sys import stdin
from keyboard import is_pressed
from termios import tcflush, TCIOFLUSH
from time import strftime

key_flag = False
cam = Picamera2()
cam.start_preview(Preview.QTGL)
cam.start()

try:
    while True:
        if is_pressed('p'):
            if key_flag is False:
                key_flag = True
            filename = strftime("%Y%m%d-%H%M%S") + '.png'
            cam.capture_file(filename, format="png", wait=None)
            print("\rCaptured {} succesfully".format(filename))
        else:
            key_flag = 0
        if is_pressed('q'):
            print("\rClosing camera...")
            break
finally:
    cam.stop_preview()
    cam.stop()
    cam.close()
    tcflush(stdin, TCIOFLUSH)
