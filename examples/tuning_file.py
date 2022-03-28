#!/usr/bin/python3

from picamera2.picamera2 import *

# Here we load up the tuning for the HQ cam and alter the default exposure profile.
# For more information on what can be changed, see chapter 5 in
# https://datasheets.raspberrypi.com/camera/raspberry-pi-camera-guide.pdf

tuning = Picamera2.load_tuning_file("imx477.json")
tuning["rpi.agc"]["exposure_modes"]["normal"] = {"shutter": [100, 66666], "gain": [1.0, 8.0]}

picam2 = Picamera2(tuning=tuning)
picam2.configure(picam2.preview_configuration())
picam2.start_preview(Preview.QTGL)
picam2.start()
time.sleep(2)
