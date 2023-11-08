#!/usr/bin/python3

# This test uses the configuration object idiom to set up the camera configuration,
# but we additionally exercise the behaviour of the SensorConfiguration object
# inside the CameraConfiguration.

# The camera mode chosen should follow the sensor configuration if that's there,
# otherwise the raw stream configuration.

from picamera2 import Picamera2

picam2 = Picamera2()

max_mode = None
min_mode = None
for mode in picam2.sensor_modes:
    if max_mode is None or mode['size'] > max_mode['size']:
        max_mode = mode
    if min_mode is None or mode['size'] < min_mode['size']:
        min_mode = mode

print("Biggest mode:", max_mode)
print("Smallest mode:", min_mode)

if max_mode['size'] != min_mode['size']:

    picam2.still_configuration.main.size = min_mode['size']
    picam2.still_configuration.raw.size = min_mode['size']
    picam2.still_configuration.raw.format = min_mode['format'].format

    picam2.configure("still")

    # Check we got the config we wanted.
    config = picam2.camera_configuration()

    if config['main']['size'] != min_mode['size']:
        print("ERROR: main stream size mismatch")

    if config['raw']['size'] != min_mode['size']:
        print("ERROR: raw stream size mismatch")

    # Now change the main and raw stream sizes.
    picam2.still_configuration.main.size = max_mode['size']
    picam2.still_configuration.raw.size = max_mode['size']
    picam2.still_configuration.raw.format = max_mode['format'].format

    picam2.configure("still")

    # The main stream size should change, but the raw stream size should be the same as before,
    # because we haven't updated the sensor config.
    config = picam2.camera_configuration()

    if config['main']['size'] != max_mode['size']:
        print("ERROR: main stream size mismatch")

    if config['raw']['size'] != min_mode['size']:
        print("ERROR: raw stream size changed unexpectedly")

    if picam2.still_configuration.raw.size != picam2.still_configuration.sensor.output_size:
        print("ERROR: raw stream and sensor sizes should match")

    # Now update the sensor config, and the raw stream should change too.
    picam2.still_configuration.sensor.output_size = max_mode['size']
    picam2.still_configuration.sensor.bit_depth = max_mode['format'].bit_depth

    picam2.configure("still")
    config = picam2.camera_configuration()

    if config['main']['size'] != max_mode['size']:
        print("ERROR: main stream size mismatch")

    if config['raw']['size'] != max_mode['size']:
        print("ERROR: raw stream has not updated")

    if picam2.still_configuration.raw.size != picam2.still_configuration.sensor.output_size:
        print("ERROR: raw stream and sensor sizes should match")

    # Final test. Let's check we can clear the sensor config out, and it will obey the
    # raw stream config again. No change to the main stream.
    picam2.still_configuration.sensor = None
    picam2.still_configuration.raw.size = min_mode['size']
    picam2.still_configuration.raw.format = min_mode['format'].format

    picam2.configure("still")
    config = picam2.camera_configuration()

    if config['main']['size'] != max_mode['size']:
        print("ERROR: main stream size mismatch")

    if config['raw']['size'] != min_mode['size']:
        print("ERROR: raw stream has been ignored")

    if picam2.still_configuration.raw.size != picam2.still_configuration.sensor.output_size:
        print("ERROR: raw stream and sensor sizes should match")

    # Actually, one more thing. Let's overwrite the sensor config in the current camera
    # config and check that the raw stream changes again. Currently it's "min_mode".

    config = picam2.camera_configuration()
    config['sensor'] = {'output_size': max_mode['size'], 'bit_depth': max_mode['format'].bit_depth}
    picam2.configure(config)

    config = picam2.camera_configuration()
    if config['raw']['size'] != max_mode['size']:
        print("ERROR: raw stream has been ignored")
