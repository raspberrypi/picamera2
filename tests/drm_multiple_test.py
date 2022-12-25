import time

from picamera2 import CameraInfo, Picamera2

if CameraInfo.n_cameras < 2:
    print("SKIPPED (one camera)")
    quit()

camera1 = Picamera2(0)
camera1.start_preview()
camera1.start()
time.sleep(1)

camera2 = Picamera2(1)
camera2.start_preview()
camera2.start()
time.sleep(1)

camera1.close()
camera1 = Picamera2(0)
camera1.start_preview()
camera1.start()
time.sleep(1)

camera2.close()
camera2 = Picamera2(1)
camera2.start_preview()
camera2.start()
time.sleep(1)

camera1.close()
camera2.close()
