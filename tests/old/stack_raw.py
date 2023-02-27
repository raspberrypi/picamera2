#!/usr/bin/python3

# This example adds multiple exposures together to create a much longer exposure
# image. It does this by adding raw images together, correcting the black level,
# and saving a DNG file. Currentl you need to use a raw converter to obtain the
# final result (e.g. "dcraw -w -W accumulated.dng").

import numpy as np
from PIL import Image

from scicamera import Camera, CameraConfig
from scicamera.sensor_format import SensorFormat

exposure_time = 60000
num_frames = 6

# Configure an unpacked raw format as these are easier to add.
camera = Camera()
raw_format = SensorFormat(camera.sensor_format)
raw_format.packing = None
config = CameraConfig.for_still(
    camera, raw={"format": raw_format.format}, buffer_count=2
)
camera.configure(config)
images = []
camera.set_controls({"ExposureTime": exposure_time // num_frames, "AnalogueGain": 1.0})
camera.start()

# The raw images can be added directly using 2-byte pixels.
for i in range(num_frames):
    images.append(camera.capture_array("raw").result().view(np.uint16))
metadata = camera.capture_metadata().result()

accumulated = images.pop(0).astype(int)
for image in images:
    accumulated += image

# Fix the black level, and convert back to uint8 form for saving as a DNG.
black_level = metadata["SensorBlackLevels"][0] / 2 ** (16 - raw_format.bit_depth)
accumulated -= (num_frames - 1) * int(black_level)
accumulated = accumulated.clip(0, 2**raw_format.bit_depth - 1).astype(np.uint16)
accumulated = accumulated.view(np.uint8)
metadata["ExposureTime"] = exposure_time

Image.fromarray(accumulated).save("accumulated.jpeg")
