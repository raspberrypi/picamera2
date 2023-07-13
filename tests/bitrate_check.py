#!/usr/bin/python3

# Check that specifying a quality causes a pre-existing bitrate to be overwritten,
# but that it stays the same when no quality is given.

import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, Quality

picam2 = Picamera2()
video_config = picam2.create_video_configuration()
picam2.configure(video_config)
encoder = H264Encoder()

picam2.start_recording(encoder, 'low.h264', quality=Quality.VERY_LOW)
bitrate_low = encoder.bitrate
time.sleep(5)
picam2.stop_recording()

picam2.start_recording(encoder, 'high.h264', quality=Quality.HIGH)
bitrate_high = encoder.bitrate
time.sleep(5)
picam2.stop_recording()

picam2.start_recording(encoder, 'high_again.h264')
bitrate_high_again = encoder.bitrate
time.sleep(5)
picam2.stop_recording()

# Now, it should be that the bitrate increased from the first recording to
# the second, but stayed the same for the third.

print(bitrate_low, bitrate_high, bitrate_high_again)
if bitrate_low >= bitrate_high or bitrate_high != bitrate_high_again:
    print("Error: bitrates not as expected")
