import time

from picamera2 import Picamera2, Preview

picam2a = Picamera2(0)
picam2a.start_preview(Preview.NULL, x=1000, y=0)
picam2a.start()
time.sleep(1)

picam2b = Picamera2(1)
picam2b.start_preview(Preview.NULL, x=1000, y=500)
picam2b.start()
time.sleep(1)

picam2a.close()
picam2a = Picamera2(0)
picam2a.start_preview(Preview.NULL, x=0, y=0)
picam2a.start()
time.sleep(1)

picam2b.close()
picam2b = Picamera2(1)
picam2b.start_preview(Preview.NULL, x=0, y=500)
picam2b.start()
time.sleep(1)

picam2a.close()
picam2b.close()
