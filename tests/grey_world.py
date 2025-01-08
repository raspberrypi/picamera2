#!/usr/bin/python3
import time

from picamera2 import Picamera2

# Here we load up the tuning for the HQ cam and alter the default exposure profile.
# For more information on what can be changed, see chapter 5 in
# https://datasheets.raspberrypi.com/camera/raspberry-pi-camera-guide.pdf

tuning = Picamera2.load_tuning_file("imx477.json")
awb = Picamera2.find_tuning_algo(tuning, "rpi.awb")
awb.clear()
awb['bayes'] = 0
picam2 = Picamera2(tuning=tuning)
picam2.configure(picam2.create_preview_configuration())
picam2.start()
time.sleep(2)
picam2.stop()
