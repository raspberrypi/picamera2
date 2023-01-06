import time

from picamera2 import Picamera2, Preview

picam2 = Picamera2()
picam2.start_preview(Preview.DRM)
picam2.start()
time.sleep(2)
picam2.stop_preview()
time.sleep(2)
picam2.start_preview(Preview.DRM)
time.sleep(2)
picam2.stop()
picam2.stop_preview()
