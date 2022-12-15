import re
from libcamera import Transform
import numpy as np


class SensorFormat:
    def __init__(self, fmt_string):
        if "_" in fmt_string:
            pixels, self.packing = fmt_string.split("_")
        else:
            pixels = fmt_string
            self.packing = None
        self.bit_depth = int(re.search("\\d+$", pixels).group())
        self.bayer_order = re.search("[RGB]+", pixels).group()

    @property
    def format(self):
        return f"{self.unpacked}{f'_{self.packing}' if self.packing else ''}"

    @property
    def unpacked(self):
        return f"{'' if self.mono else 'S'}{self.bayer_order}{self.bit_depth}"

    @property
    def mono(self):
        return self.bayer_order == "R"

    def __repr__(self):
        return self.format

    def transform(self, transform: Transform):
        if self.mono:
            return
        bayer_array = np.reshape([c for c in self.bayer_order], (2, 2))
        if transform.hflip:
            bayer_array = np.flip(bayer_array, 1)
        if transform.vflip:
            bayer_array = np.flip(bayer_array, 0)
        if transform.transpose:
            bayer_array = np.transpose(bayer_array)
        self.bayer_order = "".join(bayer_array.flatten())
