from picamera2.picamera2 import *
import time

print("Preview re-initialized after start.")
picam2 = Picamera2()
preview = picam2.preview_configuration()
picam2.configure(preview)
picam2.start()
picam2.start_preview(Preview.QT)
np_array = picam2.capture_array()
print(np_array)
time.sleep(5)
picam2.stop_preview()
picam2.close()



print("Preview initialized before start.")
picam2 = Picamera2()
preview = picam2.preview_configuration()
picam2.configure(preview)
picam2.start_preview(Preview.QT)
picam2.start()
np_array = picam2.capture_array()
print(np_array)
time.sleep(5)
picam2.stop_preview()
picam2.close()


