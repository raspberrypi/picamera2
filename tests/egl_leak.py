#!/usr/bin/python3

# Opening and closing the QTGL preview was leaking buffer handles.

import subprocess
import time

from picamera2 import Picamera2

picam2 = Picamera2()
half_res = tuple([s // 2 for s in picam2.sensor_resolution])

for _ in range(10):
    subprocess.check_call(['grep', 'Cma', '/proc/meminfo'])
    config = picam2.create_preview_configuration({'size': half_res}, raw={'size': half_res})
    picam2.configure(config)
    picam2.start(show_preview=True)
    time.sleep(1)
    picam2.stop_preview()
    picam2.stop()
