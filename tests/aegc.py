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
test_control_fixed("ExposureTime", 1000)
test_control_auto("ExposureTime")

test_control_fixed("AnalogueGain", 1.5)
test_control_fixed("AnalogueGain", 3.0)
test_control_fixed("AnalogueGain", 5.8)
test_control_auto("AnalogueGain")


# Also test that it works when we start the camera.

def test_control_start(control, value):
    controls = {control: value}
    config = picam2.create_preview_configuration(controls=controls)
    picam2.start(config)

    # The very first frame should have the given values.
    metadata = picam2.capture_metadata()
    picam2.stop()
    check = metadata[control]
    print(f"Camera started with {control} {check}")

    if abs(value - check) > 0.05 * value:
        print(f"ERROR: request {control} of {value} but got {check}")


picam2.stop()

test_control_start("ExposureTime", 12345)
test_control_start("ExposureTime", 23456)
test_control_start("AnalogueGain", 1.5)
test_control_start("AnalogueGain", 3.0)
