from concurrent.futures import Future

from scicamera import Camera
from scicamera.frame import CameraFrame

camera = Camera()

camera.start()

futures = camera.capture_serial_frames(5)

camera.stop()
camera.close()


for f in futures:
    assert isinstance(f, Future)
    assert isinstance(f.result(), CameraFrame)
