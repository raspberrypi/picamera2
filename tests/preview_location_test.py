from logging import getLogger

import numpy as np

from picamera2 import CameraConfig, Picamera2

_log = getLogger(__name__)
_log.info("Preview re-initialized after start.")
camera = Picamera2()
preview = CameraConfig.for_preview(camera)
camera.configure(preview)
camera.start()
np_array = camera.capture_array().result()
assert isinstance(np_array, np.ndarray)
_log.info(np_array)
camera.close()
