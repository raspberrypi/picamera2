def is_YUV(fmt: str) -> bool:
    return fmt in ("NV21", "NV12", "YUV420", "YVU420", "YVYU", "YUYV", "UYVY", "VYUY")

def is_RGB(fmt: str) -> bool:
    return fmt in ("BGR888", "RGB888", "XBGR8888", "XRGB8888")

def is_Bayer(fmt: str) -> bool:
    return fmt in ("SBGGR8", "SGBRG8", "SGRBG8", "SRGGB8",
                    "SBGGR10", "SGBRG10", "SGRBG10", "SRGGB10",
                    "SBGGR10_CSI2P", "SGBRG10_CSI2P", "SGRBG10_CSI2P", "SRGGB10_CSI2P",
                    "SBGGR12", "SGBRG12", "SGRBG12", "SRGGB12",
                    "SBGGR12_CSI2P", "SGBRG12_CSI2P", "SGRBG12_CSI2P", "SRGGB12_CSI2P")

def is_mono(fmt: str) -> bool:
    return fmt in ("R8", "R10", "R12", "R8_CSI2P", "R10_CSI2P", "R12_CSI2P")

def is_raw(fmt: str) -> bool:
    return is_Bayer(fmt) or is_mono(fmt)
