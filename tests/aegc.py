#!/usr/bin/python3

import time

from picamera2 import Picamera2


def test_control_fixed(control, value):
    picam2.set_controls({control: value})
    time.sleep(1.0)
    check = picam2.capture_metadata()[control]
    if abs(check - value) > value * 0.05:
        print(f"ERROR: requested {control} of {value} but got {check}")
    else:
        print(f"Requested {control} of {value}, got {check}")


def test_control_auto(control):
    current = picam2.capture_metadata()[control]
    picam2.set_controls({control: 0})
    time.sleep(1.0)
    for _ in range(5):
        check = picam2.capture_metadata()[control]
        if abs(check - current) > current * 0.05:
            print(f"Control {control} changed from {current} to {check}")
            return
    print(f"ERROR: {control} has not returned to auto - still {check}")


picam2 = Picamera2()
picam2.start()

test_control_fixed("ExposureTime", 5000)
test_control_fixed("ExposureTime", 10000)
test_control_auto("ExposureTime")

test_control_fixed("AnalogueGain", 1.5)
test_control_fixed("AnalogueGain", 3.0)
test_control_auto("AnalogueGain")
