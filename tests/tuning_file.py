#!/usr/bin/python3
import time

from picamera2 import Picamera2

# Here we load up the tuning for the HQ cam and alter the default exposure profile.
# For more information on what can be changed, see chapter 5 in
# https://datasheets.raspberrypi.com/camera/raspberry-pi-camera-guide.pdf

tuning = Picamera2.load_tuning_file("imx477.json")
algo = Picamera2.find_tuning_algo(tuning, "rpi.agc")
algo["exposure_modes"]["normal"] = {"shutter": [100, 66666], "gain": [1.0, 8.0]}

camera = Picamera2(tuning=tuning)
camera.configure(camera.create_preview_configuration())
camera.start_preview()
camera.start()
camera.discard_frames(2)
camera.close()
