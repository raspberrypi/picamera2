import time

from picamera2 import Picamera2

camera = Picamera2()
camera.start_preview()
camera.start()
time.sleep(2)
camera.stop_preview()
time.sleep(2)
camera.start_preview()
time.sleep(2)
camera.stop()
camera.stop_preview()
camera.close()
