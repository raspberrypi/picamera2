import subprocess
import sys

from picamera2 import Picamera2

# First open/close several times in this process in various ways.


def run_camera():
    camera = Picamera2()
    camera.start()
    camera.stop()
    camera.close()


run_camera()

with Picamera2() as picam2:
    picam2.start()
    picam2.stop()

picam2 = Picamera2()
picam2.start()
picam2.stop()
picam2.close()

# Check that everything is released so other processes can use the camera.

program = """from picamera2 import Picamera2
picam2 = Picamera2()
picam2.start()"""
print("Start camera in separate process:")
cmd = ["python3", "-c", program]
p = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
p.wait()
