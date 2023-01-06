#!/usr/bin/python3

# This captures a request but then switches the camera to a different mode.
# This now "old" request can still be used.

import time

from picamera2 import Picamera2

picam2 = Picamera2()
capture_config = picam2.create_still_configuration()
picam2.start(show_preview=True)

time.sleep(1)

request = picam2.switch_mode_and_capture_request(capture_config)

# Preview should be running again...
time.sleep(1)

# But we can still save the request. Don't forget to release it once you're done!
request.save("main", "test.jpg")
request.release()

picam2.stop()
