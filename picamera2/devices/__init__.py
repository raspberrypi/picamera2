try:
    # Hailo requires hailo_platform package, which may not be installed on non-Hailo platforms.
    from .hailo import Hailo
except ModuleNotFoundError:
    pass
from .imx708 import IMX708
