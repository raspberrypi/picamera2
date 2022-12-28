import time

from picamera2 import Picamera2

camera = Picamera2()
camera.start_preview()
camera.start()
camera.discard_frames(2).result()
camera.stop_preview()

time.sleep(1)

camera.start_preview()
camera.discard_frames(2).result()
camera.stop()
camera.stop_preview()


camera.close()
