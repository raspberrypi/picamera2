#!/usr/bin/python3

import time

from libcamera import controls

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder

# Show how to do software-synchronised camera recordings.
#
# This code is for the server (which controls the synchronisation), but the code
# for the client is almost identical. We just change controls.rpi.SyncModeEnum.Server
# into controls.rpi.SyncModeEnum.Client and it will listen out for and follow
# the server.
#
# Usually the best advice is to start the client first. It will sit there recording
# nothing at all until the server has been started and tells it to "go now".

picam2 = Picamera2()
ctrls = {'SyncMode': controls.rpi.SyncModeEnum.Server}
config = picam2.create_video_configuration(controls=ctrls)
encoder = H264Encoder(bitrate=5000000)
encoder.sync_enable = True  # this tells the encoder to wait until synchronisation
output = "server.h264"

picam2.start(config)
picam2.start_encoder(encoder, output)

# This event being signalled tells us that recording has started.
encoder.sync.wait()
print("Recording has started")

time.sleep(5)

picam2.stop_encoder(encoder)
picam2.stop()
