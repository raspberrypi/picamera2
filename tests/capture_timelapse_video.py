#!/usr/bin/python3
import subprocess
import time

from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder, Quality
from picamera2.outputs.fileoutput import FileOutput


# Define an output which divides all the timestamps by a factor
class TimelapseOutput(FileOutput):
    def __init__(self, file=None, pts=None, speed=10):
        self.speed = int(speed)
        super().__init__(file, pts)

    def outputtimestamp(self, timestamp):
        if timestamp == 0:
            # Print timecode format for the first line
            print("# timestamp format v2", file=self.ptsoutput, flush=True)
        # Divide each timestamp by factor to speed up playback
        timestamp //= self.speed
        super().outputtimestamp(timestamp)


# Set the parameters for the timelapse
speedup_factor = 20
framerate = 1.0
resolution = (1920, 1080)

picam2 = Picamera2()
config = picam2.create_video_configuration(main={"size": resolution})
picam2.configure(config)

encoder = MJPEGEncoder()
output = TimelapseOutput("test.mjpeg", "timestamps.txt", speedup_factor)
encoder.output = output

picam2.start()

# Give time for Aec and Awb to settle, before disabling them
time.sleep(1)
picam2.set_controls({"AeEnable": False, "AwbEnable": False, "FrameRate": framerate})
# And wait for those settings to take effect
time.sleep(1)

picam2.start_encoder(encoder, quality=Quality.VERY_HIGH)

time.sleep(20)

picam2.stop_encoder()
picam2.stop()

# Create the output mp4 video
merge = subprocess.Popen(
    [
        "mkvmerge",
        "-o",
        "timelapse.mp4",
        "--timestamps",
        "0:timestamps.txt",
        "test.mjpeg",
    ]
)
merge.wait()
