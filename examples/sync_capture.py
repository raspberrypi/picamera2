#!/usr/bin/python3

from libcamera import controls

from picamera2 import Picamera2

# Show how to do software-synchronised capture.
#
# This code is for the server (which controls the synchronisation), but the code
# for the client is almost identical. We just change controls.rpi.SyncModeEnum.Server
# into controls.rpi.SyncModeEnum.Client and it will listen out for and follow
# the server.
#
# Usually the best advice is to start the client first. It will sit there doing
# nothing at all until the server has been started and tells it "now".

picam2 = Picamera2()
ctrls = {'FrameRate': 30.0, 'SyncMode': controls.rpi.SyncModeEnum.Server}
# You can use a still capture mode, but would probably need more buffers so that
# you don't get lots of frame drops.
config = picam2.create_preview_configuration(controls=ctrls)

picam2.start(config)

req = picam2.capture_sync_request()
# THe 'timer' tells us how many microseconds we were away from the synchronisation point.
# Normally this should be small, but may be much larger if frames are being dropped.
print("Lag:", req.get_metadata()['SyncTimer'])
