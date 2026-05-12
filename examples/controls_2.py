#!/usr/bin/python3

# Another (simpler!) way to fix the AEC/AGC and AWB.

import time

from picamera2 import Picamera2, Preview

picam2 = Picamera2()
picam2.start_preview(Preview.QTGL)

preview_config = picam2.create_preview_configuration()
picam2.configure(preview_config)

picam2.start()
time.sleep(1)

ctrls = {"AeEnable": 0}
if not picam2.is_mono:
    ctrls["AwbEnable"] = 0

picam2.set_controls(ctrls)
time.sleep(5)
