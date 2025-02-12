import importlib
from enum import Enum
from types import ModuleType


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
    except ImportError:
        raise ImportError(f'{qt_module} is not installed or could not be imported.')
