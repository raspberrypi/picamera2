import importlib
import os
import sys
from enum import Enum
from logging import getLogger
from types import ModuleType

_log = getLogger(__name__)


class _QT_BINDING(Enum):
    PyQt5 = 'PyQt5'
    PyQt6 = 'PyQt6'
    PySide2 = 'PySide2'
    PySide6 = 'PySide6'


def _get_qt_modules(qt_module: _QT_BINDING) -> tuple[ModuleType, ModuleType, ModuleType]:
    """
    Gets the qt modules for the given qt binding

    Parameters
    ----------
    qt_module : _QT_BINDING
        The module we want to get Qt QtCore, QtGui, and QtWidgets modules from

    Returns
    -------
    out : tuple[ModuleType, ModuleType, ModuleType]
        A tuple containing the QtCore, QtGui, and QtWidgets modules respectively, from the given python qt module

    Notes
    -----
    - Assigns alternate attributes for Signals and Slots as these are different in PySide and PyQt
    """
    try:
        QtCoreModule = importlib.import_module('.QtCore', package=qt_module.value)
        QtGuiModule = importlib.import_module('.QtGui', package=qt_module.value)
        QtWidgetsModule = importlib.import_module('.QtWidgets', package=qt_module.value)

        if qt_module in [_QT_BINDING.PySide2, _QT_BINDING.PySide6]:
            QtCoreModule.pyqtSignal = QtCoreModule.Signal
            QtCoreModule.pyqtSlot = QtCoreModule.Slot

        return (QtCoreModule, QtGuiModule, QtWidgetsModule)
    except ImportError as e:
        raise ImportError(f'{qt_module} is not installed or could not be imported.') from e


def _resolve_binding(value) -> _QT_BINDING:
    """
    Convert a Qt binding given as a string (case insensitive) or _QT_BINDING into a _QT_BINDING

    Raises ValueError if the value does not name a supported Qt binding.
    """
    if isinstance(value, _QT_BINDING):
        return value
    if isinstance(value, str):
        for binding in _QT_BINDING:
            if binding.value.lower() == value.lower():
                return binding
    valid = ', '.join(binding.value for binding in _QT_BINDING)
    raise ValueError(f'Invalid Qt binding {value!r}, must be one of: {valid}')


def _loaded_bindings() -> list[_QT_BINDING]:
    """Return the Qt bindings that the application has already imported (without importing any)."""
    return [binding for binding in _QT_BINDING if sys.modules.get(binding.value) is not None]


def _running_app(binding: _QT_BINDING):
    """Return the running QGuiApplication of an already imported Qt binding, or None."""
    qtgui = sys.modules.get(binding.value + '.QtGui')
    return None if qtgui is None else qtgui.QGuiApplication.instance()


_warnings_given = set()


def _warn_once(message):
    if message not in _warnings_given:
        _warnings_given.add(message)
        _log.warning(message)


def _default_binding() -> _QT_BINDING:
    """
    Return the Qt binding to use where the application has not named one explicitly

    In order of precedence, this is:
    1. Picamera2.qt_binding, if the application has set it.
    2. The Qt binding the application has already imported, if there is just one (or
       just one with a running QApplication).
    3. The PICAMERA2_QT_BINDING environment variable, if set.
    4. PyQt5.
    """
    # Imported here to avoid a circular import.
    from picamera2.picamera2 import Picamera2

    loaded = _loaded_bindings()
    if Picamera2.qt_binding is not None:
        binding = _resolve_binding(Picamera2.qt_binding)
        others = [b.value for b in loaded if b != binding]
        if others:
            _warn_once(f"Picamera2.qt_binding is {binding.value} but {', '.join(others)} has also been imported")
        return binding

    if len(loaded) > 1:
        # More than one binding imported (e.g. by other libraries); prefer one that is in use.
        loaded = [b for b in loaded if _running_app(b) is not None]
    if len(loaded) == 1:
        _log.debug(f"Using Qt binding {loaded[0].value} as it has already been imported")
        return loaded[0]

    env = os.environ.get('PICAMERA2_QT_BINDING')
    binding = _resolve_binding(env) if env else _QT_BINDING.PyQt5
    if len(_loaded_bindings()) > 1:
        names = ', '.join(b.value for b in _loaded_bindings())
        _warn_once(f"Several Qt bindings have been imported ({names}), using {binding.value}")
    return binding
