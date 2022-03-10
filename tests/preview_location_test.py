from picamera2.picamera2 import Picamera2
import time

print("Preview re-initialized after start.")
picam2 = Picamera2()
preview = picam2.preview_configuration()
picam2.configure(preview)
picam2.start_camera()
picam2.start_preview('QT')
np_array = picam2.capture_array()
print(np_array)
time.sleep(10)
picam2.stop_preview()
picam2.close_camera()



print("Preview initialized before start.")
picam2 = Picamera2()
preview = picam2.preview_configuration()
picam2.configure(preview)
picam2.start_preview('QT')
picam2.start_camera()
np_array = picam2.capture_array()
print(np_array)
time.sleep(10)
picam2.stop_preview()
picam2.close_camera()


