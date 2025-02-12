# Installing Qt and OpenGL on the 64-bit Lite OS, and trying to run
# a remote preview window, causes an error here (the 32-bit Lite OS is OK).
# It may be something to do with more recent versions of python3-opengl?
# Anyway, if we carry on regardless at least the non-OpenGL preview works,
# which is in any case what is required for remote preview windows.
from logging import getLogger

from .q_picamera2 import _get_qpicamera2
from .qt_compatibility import _QT_BINDING

_log = getLogger(__name__)

try:
    from .q_gl_picamera2 import _get_qglpicamera2
except Exception:
    _log.warning("OpenGL will not be available")


# Lazy load QPicamera2 widget classes as will likely only use one or two within a given application
def __getattr__(name: str):
    # Standard Qt widgets
    if name == 'QPicamera2':
        return _get_qpicamera2(_QT_BINDING.PyQt5)
    elif name == 'Q6Picamera2':
        return _get_qpicamera2(_QT_BINDING.PyQt6)
    elif name == 'QSide2Picamera2':
        return _get_qpicamera2(_QT_BINDING.PySide2)
    elif name == 'QSide6Picamera2':
        return _get_qpicamera2(_QT_BINDING.PySide6)
    # OpenGL accelerated Qt widgets
    elif name == 'QGlPicamera2':
        return _get_qglpicamera2(_QT_BINDING.PyQt5)
    elif name == 'QGl6Picamera2':
        return _get_qglpicamera2(_QT_BINDING.PyQt6)
    elif name == 'QGlSide2Picamera2':
        return _get_qglpicamera2(_QT_BINDING.PySide2)
    elif name == 'QGlSide6Picamera2':
        return _get_qglpicamera2(_QT_BINDING.PySide6)
    raise AttributeError(f"qt has no attribute '{name}'")
