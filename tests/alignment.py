#!/usr/bin/python3

from picamera2 import Picamera2, Platform

picam2 = Picamera2()


def compute_expected_stride(width, format):
    if format in ("BGR888", "RGB888"):
        return width * 3
    elif format in ("XBGR8888", "XRGB8888"):
        return width * 4
    elif format in ("YUV420", "YVU420"):
        return width
    elif format in ("RGB161616", "BGR161616"):
        return width * 6


def test_alignment(width, format):
    config = picam2.create_preview_configuration({'size': (width, 480), 'format': format}, buffer_count=1)
    picam2.align_configuration(config)
    picam2.configure(config)
    actual_stride = config['main']['stride']
    actual_width = config['main']['size'][0]
    expected_stride = compute_expected_stride(actual_width, format)
    if actual_stride != expected_stride:
        print("ERROR: stride", actual_stride, "!=", expected_stride, "for format", format)
        return 1
    return 0


formats = ["RGB888", "XRGB8888", "YUV420"]
if picam2.platform == Platform.PISP:
    formats.append("RGB161616")

failures = 0
for format in formats:
    for width in range(512, 1025, 2):
        print(format)
        failures += test_alignment(width, format)

print("Failures:", failures)
