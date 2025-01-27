#!/usr/bin/python3

import io
import time

from libcamera import controls

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput

picam2 = Picamera2()
ctrls = {'SyncMode': controls.rpi.SyncModeEnum.Server, 'SyncFrames': 300}
config = picam2.create_video_configuration(controls=ctrls)
encoder = H264Encoder(bitrate=5000000)
encoder.sync_enable = True  # this tells the encoder to wait until synchronisation
buffer = io.BytesIO()
output = FileOutput(buffer)

picam2.start(config)
picam2.start_encoder(encoder, output)

# The synchronisation delay is now 300 frames, or 10 seconds at 30fps, so
# for 5 seconds we can be quite sure that nothing should be recorded.

time.sleep(5)
if buffer.tell():
    print("ERROR: bytes recorded before synchronisation")
else:
    print("No bytes during synchronisation period")

encoder.sync.wait()
print("Recording has started")

# Now, if we wait a bit longer, there had better be some data!

time.sleep(5)
if buffer.tell():
    print(buffer.tell(), "bytes record after synchronisation period")
else:
    print("ERROR: still no bytes after synchronisation")

picam2.stop_encoder(encoder)
picam2.stop()
