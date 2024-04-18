YUV_FORMATS = {"NV21", "NV12", "YUV420", "YVU420",
               "YVYU", "YUYV", "UYVY", "VYUY"}

RGB_FORMATS = {"BGR888", "RGB888", "XBGR8888", "XRGB8888", "RGB161616", "BGR161616"}

BAYER_FORMATS = {"SBGGR8", "SGBRG8", "SGRBG8", "SRGGB8",
                 "SBGGR10", "SGBRG10", "SGRBG10", "SRGGB10",
                 "SBGGR10_CSI2P", "SGBRG10_CSI2P", "SGRBG10_CSI2P", "SRGGB10_CSI2P",
                 "SBGGR12", "SGBRG12", "SGRBG12", "SRGGB12",
                 "SBGGR12_CSI2P", "SGBRG12_CSI2P", "SGRBG12_CSI2P", "SRGGB12_CSI2P",
                 "BGGR_PISP_COMP1", "GBRG_PISP_COMP1", "GRBG_PISP_COMP1", "RGGB_PISP_COMP1",
                 "SBGGR16", "SGBRG16", "SGRBG16", "SRGGB16", }

MONO_FORMATS = {"R8", "R10", "R12", "R16", "R8_CSI2P", "R10_CSI2P", "R12_CSI2P"}

ALL_FORMATS = YUV_FORMATS | RGB_FORMATS | BAYER_FORMATS | MONO_FORMATS


def is_YUV(fmt: str) -> bool:
    return fmt in YUV_FORMATS


def is_RGB(fmt: str) -> bool:
    return fmt in RGB_FORMATS


def is_Bayer(fmt: str) -> bool:
    return fmt in BAYER_FORMATS


def is_mono(fmt: str) -> bool:
    return fmt in MONO_FORMATS


def is_raw(fmt: str) -> bool:
    return is_Bayer(fmt) or is_mono(fmt)


def assert_format_valid(fmt: str) -> None:
    if fmt not in ALL_FORMATS:
        raise ValueError(f"Invalid format: {fmt}. Valid formats are: {ALL_FORMATS}")
