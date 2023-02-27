import time

from scicamera import Camera, CameraInfo

if CameraInfo.n_cameras < 2:
    print("SKIPPED (one camera)")
    quit()

camera1 = Camera(0)
camera1.start_preview()
camera1.start()
time.sleep(1)

camera2 = Camera(1)
camera2.start_preview()
camera2.start()
time.sleep(1)

camera1.close()
camera1 = Camera(0)
camera1.start_preview()
camera1.start()
time.sleep(1)

camera2.close()
camera2 = Camera(1)
camera2.start_preview()
camera2.start()
time.sleep(1)

camera1.close()
camera2.close()
