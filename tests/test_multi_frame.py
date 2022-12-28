from concurrent.futures import Future

from picamera2 import Picamera2
from picamera2.frame import CameraFrame

camera = Picamera2()

camera.start()

futures = camera.capture_serial_frames(5)

camera.stop()
camera.close()


for f in futures:
    assert isinstance(f, Future)
    assert isinstance(f.result(), CameraFrame)
