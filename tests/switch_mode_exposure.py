import time

from picamera2 import Picamera2

picam2 = Picamera2()
if 'imx708' in picam2.camera_properties['Model']:
    print("SKIPPED (imx708)")
    quit()

# Select the smallest full FoV mode for the preview.
preview_mode = None
for mode in picam2.sensor_modes:
    if mode['crop_limits'][:2] == (0, 0) and \
       (preview_mode is None or mode['size'][0] < preview_mode['size'][0]):
        preview_mode = mode
print("Preview mode:", preview_mode)

preview_config = picam2.create_preview_configuration(raw=preview_mode)
still_config = picam2.create_still_configuration(buffer_count=2)

picam2.start()
time.sleep(1)
preview_metadata = picam2.capture_metadata()

picam2.switch_mode(still_config)
time.sleep(1)
still_metadata = picam2.capture_metadata()
picam2.stop()

preview_exp = preview_metadata['ExposureTime']
preview_gain = preview_metadata['AnalogueGain']
still_exp = still_metadata['ExposureTime']
still_gain = still_metadata['AnalogueGain']

print("Exposures", preview_exp, still_exp)
print("Gain", preview_gain, still_gain)

tol = 0.05
if still_exp < (1 - tol) * preview_exp or still_exp > (1 + tol) * preview_exp:
    print("ERROR: unreasonable change in exposure,", preview_exp, "vs", still_exp)
if still_gain < (1 - tol) * preview_gain or still_gain > (1 + tol) * preview_gain:
    print("ERROR: unreasonable change in gain,", preview_gain, "vs", still_gain)
