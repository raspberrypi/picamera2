import re


class SensorFormat():
    def __init__(self, fmt_string):
        pixels, self.packing = fmt_string.split("_")
        self.bit_depth = int(re.search("\\d+$", pixels).group())
        self.arrangement = re.search("[RGB]+", pixels).group()

    @property
    def format(self):
        return f"{self.unpacked}{f'_{self.packing}' if self.packing else ''}"

    @property
    def unpacked(self):
        return f"S{self.arrangement}{self.bit_depth}"

    def __repr__(self):
        return self.format
