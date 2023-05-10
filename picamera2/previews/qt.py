# Installing Qt and OpenGL on the 64-bit Lite OS, and trying to run
# a remote preview window, causes an error here (the 32-bit Lite OS is OK).
# It may be something to do with more recent versions of python3-opengl?
# Anyway, if we carry on regardless at least the non-OpenGL preview works,
# which is in any case what is required for remote preview windows.
from logging import getLogger

from .q_picamera2 import QPicamera2

_log = getLogger(__name__)

try:
    from .q_gl_picamera2 import QGlPicamera2
except Exception:
    _log.warning("OpenGL will not be available")
