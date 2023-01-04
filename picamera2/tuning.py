from __future__ import annotations

import json
import os
import tempfile


def load_tuning_file(tuning_file: str, dir=None):
    """Load the named tuning file.

    If dir is given, then only that directory is checked,
    otherwise a list of likely installation directories is searched

    :param tuning_file: Tuning file
    :type tuning_file: str
    :param dir: Directory of tuning file, defaults to None
    :type dir: str, optional
    :raises RuntimeError: Produced if tuning file not found
    :return: Dictionary of tuning file
    :rtype: dict
    """
    if dir is not None:
        dirs = [dir]
    else:
        dirs = [
            "/home/pi/libcamera/src/ipa/raspberrypi/data",
            "/usr/local/share/libcamera/ipa/raspberrypi",
            "/usr/share/libcamera/ipa/raspberrypi",
        ]
    for dir in dirs:
        file = os.path.join(dir, tuning_file)
        if os.path.isfile(file):
            with open(file, "r") as fp:
                return json.load(fp)
    raise RuntimeError("Tuning file not found")


def find_tuning_algo(tuning: dict, name: str) -> dict:
    """
    Return the parameters for the named algorithm in the given camera tuning.

    :param tuning: The camera tuning object
    :type tuning: dict
    :param name: The name of the algorithm
    :type name: str
    :rtype: dict
    """
    version = tuning.get("version", 1)
    if version == 1:
        return tuning[name]
    return next(algo for algo in tuning["algorithms"] if name in algo)[name]


class TuningContext:
    def __init__(self, tuning: str | dict | None):
        self.tuning = tuning

    def __enter__(self):
        self._tuning_file = None
        if self.tuning is None:
            os.environ.pop("LIBCAMERA_RPI_TUNING_FILE", None)  # Use default tuning
            return

        if isinstance(self.tuning, str):
            os.environ["LIBCAMERA_RPI_TUNING_FILE"] = self.tuning
        else:
            self._tuning_file = tempfile.NamedTemporaryFile("w")
            json.dump(self.tuning, self._tuning_file)
            self._tuning_file.flush()  # but leave it open as closing it will delete it
            os.environ["LIBCAMERA_RPI_TUNING_FILE"] = self._tuning_file.name

    def __exit__(self, *args):
        if self._tuning_file is not None:
            self._tuning_file.close()  # delete the temporary file
