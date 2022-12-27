from picamera2 import Picamera2
from picamera2.testing import mature_after_frames_or_timeout

camera = Picamera2()
try:
    mature_after_frames_or_timeout(camera, 10, 0.5)
except TimeoutError:
    print("Timed out! (expected)")

camera.start()

mature_after_frames_or_timeout(camera, 2, 5).result()
