import time

from libcamera import controls

from picamera2 import Picamera2

picam2 = Picamera2()
if 'AfMode' not in picam2.camera_controls:
    print("SKIPPED (no AF available)")
    quit()
print("AF available")

picam2.start()

# Initially, AfState should be Idle.
if picam2.capture_metadata()['AfState'] != controls.AfStateEnum.Idle:
    print("ERROR: AfState should initially be Idle")
print("AF idle")

# We should be able to set the lens position and see it reported back.
picam2.set_controls({'LensPosition': 1.5, 'FrameRate': 30})
time.sleep(0.5)
lp = picam2.capture_metadata()['LensPosition']
if lp < 1.45 or lp > 1.55:
    print("ERROR: lens position", lp, "should be 1.5")
print("Lens responding")

# In continuous mode, the state should be one of: Scanning, Focused or Failed. Wait for
# it to leave the Idle state.
picam2.set_controls({'AfMode': controls.AfModeEnum.Continuous})
for _ in range(10):
    state = picam2.capture_metadata()['AfState']
    if state != controls.AfStateEnum.Idle:
        break
print("Continuous AF started")

# Now sample the state a few times to make sure we get expected values.
for _ in range(5):
    time.sleep(1)
    state = picam2.capture_metadata()['AfState']
    if state not in (controls.AfStateEnum.Scanning, controls.AfStateEnum.Focused, controls.AfStateEnum.Failed):
        print("ERROR: unexpected state", state, "during continuous AF")
    else:
        print("Continuous AF state is", state)
    # Try "pausing" it.
    picam2.set_controls({'AfPause': controls.AfPauseEnum.Deferred})
    time.sleep(0.3)
    state = picam2.capture_metadata()['AfPauseState']
    if state not in (controls.AfPauseStateEnum.Paused, controls.AfPauseStateEnum.Pausing):
        print("ERROR: continuous AF pause failure, got", state)
    else:
        print("Pause OK")
    picam2.set_controls({'AfPause': controls.AfPauseEnum.Resume})

# Need this to be sure "resume" happens before going to manual mode.
time.sleep(0.2)

# Do a few regular "auto" AF cycles. Each should end with Focused or Failed.
for i in range(10):
    picam2.set_controls({'AfMode': controls.AfModeEnum.Manual, 'LensPosition': i})
    time.sleep(0.5)
    lp = picam2.capture_metadata()['LensPosition']
    if lp < i - 0.05 or lp > i + 0.05:
        print("ERROR: expected lens position", i, "got", lp)
    print("Try AF cycle from lens position", i)
    result = picam2.autofocus_cycle()
    state = picam2.capture_metadata()['AfState']
    if result and state != controls.AfStateEnum.Focused:
        print("ERROR: AF cycle succeeded but incorrect state", state)
    if not result and state != controls.AfStateEnum.Failed:
        print("ERROR: AF cycle failed but incorrect state", state)

# Finally let's set all those other AF controls to make sure that works. Though we don't
# particularly have the means to verify that they actually have the expected effect.

print("Test AfSpeed")
picam2.set_controls({'AfSpeed': controls.AfSpeedEnum.Fast})
time.sleep(0.1)
picam2.set_controls({'AfSpeed': controls.AfSpeedEnum.Normal})
time.sleep(0.1)

print("Test AfRange")
picam2.set_controls({'AfRange': controls.AfRangeEnum.Macro})
time.sleep(0.1)
picam2.set_controls({'AfRange': controls.AfRangeEnum.Full})
time.sleep(0.1)
picam2.set_controls({'AfRange': controls.AfRangeEnum.Normal})
time.sleep(0.1)

print("Test AfMetering")
picam2.set_controls({'AfMetering': controls.AfMeteringEnum.Auto})
time.sleep(0.1)
picam2.set_controls({'AfMetering': controls.AfMeteringEnum.Windows})
time.sleep(0.1)

print("Test AfWindows")
_, max_window, _ = picam2.camera_controls['ScalerCrop']
picam2.set_controls({'AfWindows': [max_window]})
time.sleep(0.1)
