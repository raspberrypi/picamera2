#!/usr/bin/python3

import time

import cv2
import numpy as np

from picamera2 import Picamera2

# Simple Mertens merge with 3 exposures. No image alignment or anything fancy.
RATIO = 3.0

picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration())
picam2.start()

# Run for a second to get a reasonable "middle" exposure level.
time.sleep(1)
metadata = picam2.capture_metadata()
exposure_normal = metadata["ExposureTime"]
gain = metadata["AnalogueGain"] * metadata["DigitalGain"]
picam2.stop()
controls = {"ExposureTime": exposure_normal, "AnalogueGain": gain}
capture_config = picam2.create_preview_configuration(
    main={"size": (1024, 768), "format": "RGB888"}, controls=controls
)
picam2.configure(capture_config)
picam2.start()
normal = picam2.capture_array()
picam2.stop()

exposure_short = int(exposure_normal / RATIO)
picam2.set_controls({"ExposureTime": exposure_short, "AnalogueGain": gain})
picam2.start()
short = picam2.capture_array()
picam2.stop()

exposure_long = int(exposure_normal * RATIO)
picam2.set_controls({"ExposureTime": exposure_long, "AnalogueGain": gain})
picam2.start()
long = picam2.capture_array()
picam2.stop()

merge = cv2.createMergeMertens()
merged = merge.process([short, normal, long])
merged = np.clip(merged * 255, 0, 255).astype(np.uint8)
cv2.imwrite("normal.jpg", normal)
cv2.imwrite("merged.jpg", merged)
