import logging
import time
from logging.handlers import TimedRotatingFileHandler

"""
Console Level Options
0 = Only print errors and critical messages to console.
1 = Print all info, errors, and critical messages to console.
2 = Print all debug, info, errors, and critical messages to console.
"""


def initialize_logger(console_level):
    logger = logging.getLogger('picamera2')
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        console = logging.StreamHandler()
        if console_level == 0:
            console.setLevel(logging.ERROR)
        elif console_level == 1:
            console.setLevel(logging.INFO)
        elif console_level == 2:
            console.setLevel(logging.DEBUG)
        else:
            raise ValueError("Console level must be an int between 0-2.")
        dtfmt = '%Y-%m-%dT%H:%M:%S'
        strfmt = '%(asctime)s.%(msecs)03dZ | %(levelname)-8s | %(message)s'
        console_fmt = logging.Formatter(strfmt, datefmt=dtfmt)
        console_fmt.converter = time.gmtime
        console.setFormatter(console_fmt)
        logger.addHandler(console)
    if logger:
        return logger
    else:
        raise ReferenceError("Logger not found.")
