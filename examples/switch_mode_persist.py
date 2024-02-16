#!/usr/bin/python3

# Switch between modes without reallocating buffers.

import time

from picamera2 import Picamera2
from picamera2.allocators import PersistentAllocator

picam2 = Picamera2(allocator=PersistentAllocator())

# Create preview configuration
preview_config = picam2.create_preview_configuration()
picam2.configure(preview_config)

# Create full resolution preview configuration
full_res_config = picam2.create_preview_configuration(
    main={"size": picam2.sensor_resolution}, buffer_count=2, use_case="full_res_preview"
)
picam2.configure(full_res_config)

# Create still configuration
still_config = picam2.create_still_configuration()
picam2.configure(still_config)

# Use preview configuration
picam2.configure(preview_config)
picam2.start()
time.sleep(2)
picam2.stop()

# Use other configuration
picam2.configure(full_res_config)
picam2.start()
time.sleep(2)
picam2.stop()

# Back to preview
picam2.configure(preview_config)
picam2.start()
# Delete other buffers to free up space
picam2.allocator.deallocate("full_res_preview")
time.sleep(2)

# Capture image with still configuration
picam2.switch_mode_and_capture_file(still_config, "test.jpg")

time.sleep(1)
picam2.stop()
