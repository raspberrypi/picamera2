import re


class SensorFormat():
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
        return f"S{self.bayer_order}{self.bit_depth}"

    def __repr__(self):
        return self.format
