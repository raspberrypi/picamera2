#!/usr/bin/python3

from picamera2 import Picamera2
import time

picam2 = Picamera2()
picam2.start(show_preview=True)
time.sleep(0.5)

# Or you could do this before starting the camera.
picam2.title_fields = ["ExposureTime", "AnalogueGain", "DigitalGain"]
time.sleep(2)

# And you can change it too.
picam2.title_fields = ["ColourTemperature", "ColourGains"]
time.sleep(2)
