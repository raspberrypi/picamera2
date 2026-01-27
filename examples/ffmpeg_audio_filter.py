#!/usr/bin/python3
import time

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput

picam2 = Picamera2()
video_config = picam2.create_video_configuration()
picam2.configure(video_config)
encoder = H264Encoder(10000000)

# audio filter takes the left channel and copies it to the right channel
# below example copies c0 (left channel) to c1 (right channel) - convert mono to stereo

# or add audio delay on left channel like this: audio_filter="pan=stereo|adelay=1500|0"
# source for more examples: https://ffmpeg.org/ffmpeg-filters.html#Examples-2
output = FfmpegOutput(
    'ffmpeg_audio_filter_test.mp4',
    audio=True,
    audio_filter="pan=stereo|c0=c0|c1=c0"
)

picam2.start_recording(encoder, output)
time.sleep(10)
picam2.stop_recording()
