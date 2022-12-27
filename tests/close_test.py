import subprocess
import sys

from picamera2 import Picamera2

# First open/close several times in this process in various ways.


def run_camera():
    camera = Picamera2()
    camera.start()
    camera.discard_frames(5)
    camera.stop()
    camera.close()


run_camera()

with Picamera2() as camera:
    camera.start()
    camera.stop()

camera = Picamera2()
camera.start()
camera.discard_frames(5)
camera.stop()
camera.close()

# Check that everything is released so other processes can use the camera.

program = """from picamera2 import Picamera2
camera = Picamera2()
camera.start()
camera.discard_frames(5)
camera.stop()
"""
print("Start camera in separate process:")
cmd = ["python3", "-c", program]
p = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
assert p.wait() == 0
