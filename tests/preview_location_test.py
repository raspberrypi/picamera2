import time

from picamera2 import Picamera2, Preview

print("Preview re-initialized after start.")
picam2 = Picamera2()
preview = picam2.create_preview_configuration()
picam2.configure(preview)
picam2.start_preview(Preview.QT)
picam2.start()
np_array = picam2.capture_array()
print(np_array)
time.sleep(5)
picam2.stop_preview()
picam2.close()

print("Preview initialized before start.")
picam2 = Picamera2()
preview = picam2.create_preview_configuration()
picam2.configure(preview)
picam2.start_preview(Preview.QT)
picam2.start()
np_array = picam2.capture_array()
print(np_array)
time.sleep(5)
picam2.stop_preview()
picam2.close()
