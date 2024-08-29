#!/usr/bin/python3

import io
import os
import time

import cv2

from picamera2 import MappedArray, Picamera2
from picamera2.encoders import H264Encoder, JpegEncoder, MJPEGEncoder, Quality
from picamera2.outputs import FileOutput

# Check that low quality streams come out smaller than high quality ones! This is of
# course dependent on the images returned by the camera, but hopefully the difference
# between very low/high is so great that the behaviour should be reliable enough.


# If ASSET_DIR is set, we can inject this file instead of using camera images.
FILENAME = "quality_check.mp4"
FRAMES = []
COUNTER = 0
SIZE = (640, 360)
if os.environ.get('ASSET_DIR') is not None:
    filename = os.path.join(os.path.expanduser(os.environ['ASSET_DIR']), FILENAME)
    if os.path.isfile(filename):
        print("Using file", filename)
        cap = cv2.VideoCapture(filename)
        while len(FRAMES) < 100:
            ret, frame = cap.read()
            if not ret:
                break
            if frame.shape != (SIZE[1], SIZE[0], 3):
                frame = cv2.resize(frame, dsize=SIZE)
            FRAMES.append(frame)
else:
    print("Using camera")


def callback(request):
    if FRAMES:
        global COUNTER
        with MappedArray(request, 'main') as m:
            m.array[...] = FRAMES[COUNTER]
        COUNTER = (COUNTER + 1) % len(FRAMES)


def do_encode(encoder, quality):
    global COUNTER
    COUNTER = 0
    data = io.BytesIO()
    picam2.start_encoder(encoder, output=FileOutput(data), name='main', quality=quality)
    time.sleep(time_seconds)
    picam2.stop_encoder(encoder)
    return data.getbuffer().nbytes


picam2 = Picamera2()
config = picam2.create_video_configuration({'format': 'RGB888', 'size': SIZE}, lores={'size': SIZE})
picam2.configure(config)
picam2.start()
picam2.pre_callback = callback
time_seconds = 5

low_quality = do_encode(MJPEGEncoder(), Quality.VERY_LOW)
high_quality = do_encode(MJPEGEncoder(), Quality.VERY_HIGH)
print("MJPEGEncoder: low quality", low_quality, "high quality", high_quality)
if (1.5 * low_quality > high_quality):
    print("Error: MJPEGEncoder file sizes not as expected")

low_quality = do_encode(H264Encoder(), Quality.VERY_LOW)
high_quality = do_encode(H264Encoder(), Quality.VERY_HIGH)
print("H264Encoder: low quality", low_quality, "high quality", high_quality)
if (1.5 * low_quality > high_quality):
    print("Error: H264Encoder file sizes not as expected")

low_quality = do_encode(JpegEncoder(), Quality.VERY_LOW)
high_quality = do_encode(JpegEncoder(), Quality.VERY_HIGH)
print("JpegEncoder: low quality", low_quality, "high quality", high_quality)
if (1.5 * low_quality > high_quality):
    print("Error: JpegEncoder file sizes not as expected")
