import time
from logging import getLogger

from picamera2 import Picamera2, Preview

wait = 2
buffer = 1

_log = getLogger(__name__)

# First we create a camera instance.
camera = Picamera2()

# Let's set it up for previewing.
preview = camera.create_preview_configuration()
camera.configure(preview)

camera.start(show_preview=None)

null1 = time.monotonic()
print("Null Preview")
time.sleep(buffer)
camera.start_preview(Preview.NULL)
time.sleep(wait)
camera.stop_preview()
null2 = time.monotonic()

# Close the camera.
camera.close()

_log.info(f"Null Cycle Results: {null2-null1-wait-buffer} s")
