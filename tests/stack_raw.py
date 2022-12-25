#!/usr/bin/python3

# This example adds multiple exposures together to create a much longer exposure
# image. It does this by adding raw images together, correcting the black level,
# and saving a DNG file. Currentl you need to use a raw converter to obtain the
# final result (e.g. "dcraw -w -W accumulated.dng").

import numpy as np

from picamera2 import Picamera2
from picamera2.sensor_format import SensorFormat

exposure_time = 60000
num_frames = 6

# Configure an unpacked raw format as these are easier to add.
picam2 = Picamera2()
raw_format = SensorFormat(picam2.sensor_format)
raw_format.packing = None
config = picam2.create_still_configuration(
    raw={"format": raw_format.format}, buffer_count=2
)
picam2.configure(config)
images = []
picam2.set_controls({"ExposureTime": exposure_time // num_frames, "AnalogueGain": 1.0})
picam2.start()

# The raw images can be added directly using 2-byte pixels.
for i in range(num_frames):
    images.append(picam2.capture_array("raw").view(np.uint16))
metadata = picam2.capture_metadata()

accumulated = images.pop(0).astype(int)
for image in images:
    accumulated += image

# Fix the black level, and convert back to uint8 form for saving as a DNG.
black_level = metadata["SensorBlackLevels"][0] / 2 ** (16 - raw_format.bit_depth)
accumulated -= (num_frames - 1) * int(black_level)
accumulated = accumulated.clip(0, 2**raw_format.bit_depth - 1).astype(np.uint16)
accumulated = accumulated.view(np.uint8)
metadata["ExposureTime"] = exposure_time
picam2.helpers.save(accumulated, metadata, "accumulated.jpeg")
