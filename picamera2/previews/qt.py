# Installing Qt and OpenGL on the 64-bit Lite OS, and trying to run
# a remote preview window, causes an error here (the 32-bit Lite OS is OK).
# It may be something to do with more recent versions of python3-opengl?
# Anyway, if we carry on regardless at least the non-OpenGL preview works,
# which is in any case what is required for remote preview windows.
import os
from logging import getLogger

from .q_picamera2 import _get_qpicamera2
from .qt_compatibility import _QT_BINDING

_log = getLogger(__name__)

try:
    from .q_gl_picamera2 import _get_qglpicamera2
    from .q_gl_picamera2_wl import _get_qglpicamera2_wl
    from .q_gl_picamera2_wl_direct import _get_qglpicamera2_wl_direct
except Exception:
    _log.warning("OpenGL will not be available")


def is_wayland_gl_widget(widget) -> bool:
    """Return True if widget is a native-Wayland GL camera widget.

    Works for both QGlPicamera2Wl (FBO path) and QGlPicamera2WlDirect.
    Returns False for the X11 QGlPicamera2, for non-GL widgets, for None,
    and if the OpenGL dependencies are not installed.
    """
    try:
        from picamera2.previews.gl_helpers import _WaylandGlWidget

        return isinstance(widget, _WaylandGlWidget)
    except ImportError:
        return False


def _is_wayland():
    """Return True if Qt is using (or should use) the native Wayland backend.

    Priority order:
    1. Explicit QT_QPA_PLATFORM override (set QT_QPA_PLATFORM=xcb to force X11).
    2. The actual platform of a already-running QApplication — ensures embedded
       apps get the widget that matches their Qt backend regardless of env vars.
    3. Auto-detect from WAYLAND_DISPLAY (standalone preview path, where no
       QApplication exists yet when the widget factory is first called).
    """
    explicit = os.environ.get('QT_QPA_PLATFORM')
    if explicit:
        return explicit == 'wayland'
    import importlib

    for pkg in ('PyQt5.QtGui', 'PyQt6.QtGui', 'PySide2.QtGui', 'PySide6.QtGui'):
        try:
            app = importlib.import_module(pkg).QGuiApplication.instance()
            if app is not None:
                return app.platformName() == 'wayland'
        except ImportError:
            continue
    return bool(os.environ.get('WAYLAND_DISPLAY'))


def _make_gl_factory(binding):
    """Return a platform-transparent callable for the GL camera widget.

    On Wayland dispatches to QGlPicamera2Wl (or QGlPicamera2WlDirect when
    direct=True); on X11/XWayland dispatches to the existing QGlPicamera2.
    The direct parameter is silently ignored on X11 (no direct variant exists
    there).
    """

    def factory(picam2, direct=False, **kwargs):
        if _is_wayland():
            if direct:
                return _get_qglpicamera2_wl_direct(binding)(picam2, **kwargs)
            return _get_qglpicamera2_wl(binding)(picam2, **kwargs)
        return _get_qglpicamera2(binding)(picam2, **kwargs)

    return factory


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
    # Platform-transparent GL widgets: native Wayland on Wayland, X11 otherwise.
    # Pass direct=True to request the QOpenGLWindow direct-render path on Wayland.
    elif name == 'QGlPicamera2':
        return _make_gl_factory(_QT_BINDING.PyQt5)
    elif name == 'QGl6Picamera2':
        return _make_gl_factory(_QT_BINDING.PyQt6)
    elif name == 'QGlSide6Picamera2':
        return _make_gl_factory(_QT_BINDING.PySide6)
    elif name == 'QGlSide2Picamera2':
        # No Wayland variant for PySide2; X11/XWayland only.
        return _get_qglpicamera2(_QT_BINDING.PySide2)
    # Explicit Wayland-only GL widgets (for apps that need to name the backend directly)
    elif name == 'QGlPicamera2Wl':
        return _get_qglpicamera2_wl(_QT_BINDING.PyQt5)
    elif name == 'QGl6Picamera2Wl':
        return _get_qglpicamera2_wl(_QT_BINDING.PyQt6)
    elif name == 'QGlSide6Picamera2Wl':
        return _get_qglpicamera2_wl(_QT_BINDING.PySide6)
    elif name == 'QGlPicamera2WlDirect':
        return _get_qglpicamera2_wl_direct(_QT_BINDING.PyQt5)
    elif name == 'QGl6Picamera2WlDirect':
        return _get_qglpicamera2_wl_direct(_QT_BINDING.PyQt6)
    elif name == 'QGlSide6Picamera2WlDirect':
        return _get_qglpicamera2_wl_direct(_QT_BINDING.PySide6)
    raise AttributeError(f"qt has no attribute '{name}'")
