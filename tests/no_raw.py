#!/usr/bin/python3

# By default we ask for raw streams, but here we test that we can also run without.

from picamera2 import Picamera2

picam2 = Picamera2()

# Try a preview config.
config = picam2.create_preview_configuration(raw=None)
print("Test config", config)
if config['raw'] is not None:
    print("ERROR: configuration has an unexpected raw stream")
picam2.configure(config)
picam2.start()

for _ in range(30):
    picam2.capture_metadata()
array = picam2.capture_array('main')

picam2.stop()

# Now try a preview config with a lores stream.
config = picam2.create_preview_configuration(lores={}, raw=None)
print("Test config", config)
if config['raw'] is not None:
    print("ERROR: configuration has an unexpected raw stream")
picam2.configure(config)
picam2.start()

for _ in range(30):
    picam2.capture_metadata()
array = picam2.capture_array('main')
array = picam2.capture_array('lores')

picam2.stop()

# Try a still configuration.
config = picam2.create_still_configuration(raw=None)
print("Test config", config)
if config['raw'] is not None:
    print("ERROR: configuration has an unexpected raw stream")
picam2.configure(config)
picam2.start()

for _ in range(10):
    picam2.capture_metadata()
array = picam2.capture_array('main')

picam2.stop()

# And a still configuration with a lores stream.
config = picam2.create_still_configuration(lores={'size': (640, 480)}, raw=None)
print("Test config", config)
if config['raw'] is not None:
    print("ERROR: configuration has an unexpected raw stream")
picam2.configure(config)
picam2.start()

for _ in range(10):
    picam2.capture_metadata()
array = picam2.capture_array('main')
array = picam2.capture_array('lores')

picam2.stop()

picam2.close()
