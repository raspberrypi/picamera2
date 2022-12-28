from logging import getLogger

import numpy as np

from picamera2 import Picamera2

_log = getLogger(__name__)
_log.info("Preview re-initialized after start.")
camera = Picamera2()
preview = camera.create_preview_configuration()
camera.configure(preview)
camera.start()
np_array = camera.capture_array().result()
assert isinstance(np_array, np.ndarray)
_log.info(np_array)
camera.close()
