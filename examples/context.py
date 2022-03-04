from picamera2 import Picamera2
from null_preview import NullPreview
import time


with Picamera2(0, verbose=1) as picam2:
    config = picam2.still_configuration()
    picam2.configure(config)

    preview = NullPreview(picam2)

    picam2.start()

    np_array = picam2.capture_array()
    print(np_array)
    picam2.capture_file(f"context_demo.jpg")
    time.sleep(1)