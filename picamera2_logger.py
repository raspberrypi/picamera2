import logging
from logging.handlers import TimedRotatingFileHandler
import time

"""
Console Level Options
0 = Only print errors and critical messages to console.
1 = Print all info, errors, and critical messages to console.
2 = Print all debug, info, errors, and critical messages to console.

Log Level Options
0 = Don't create a log file.
1 = Create a log file. File is named picamera2.log.YYYYMMDD. 
"""


def initialize_logger(console_level, log_level):
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
        if log_level == 1:
            trfh = TimedRotatingFileHandler('picamera2.log', when='midnight',
                                            interval=1, backupCount=7)
            trfh.setLevel(logging.DEBUG)
            dtfmt = '%Y-%m-%dT%H:%M:%S'
            trfh_fmt = logging.Formatter('%(asctime)s.%(msecs)03dZ | %(levelname)-8s | %(message)s', datefmt=dtfmt)
            trfh_fmt.converter = time.gmtime
            trfh.setFormatter(trfh_fmt)
            logger.addHandler(trfh)
        dtfmt = '%Y-%m-%dT%H:%M:%S'
        console_fmt = logging.Formatter('%(asctime)s.%(msecs)03dZ | %(levelname)-8s | %(message)s', datefmt=dtfmt)
        console_fmt.converter = time.gmtime
        console.setFormatter(console_fmt)
        logger.addHandler(console)
    if logger:
        return logger
    else:
        raise ReferenceError("Logger not found.")
