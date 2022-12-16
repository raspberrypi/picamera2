#!/usr/bin/python3
import time

import numpy as np
from pidng.core import RAW2DNG, DNGTags, Tag
from pidng.defs import *
from PIL import Image

from picamera2 import Picamera2
from picamera2.encoders import Encoder

size = (2592, 1944)
picam2 = Picamera2()
video_config = picam2.create_video_configuration(
    raw={"format": "SGBRG10", "size": size}
)
picam2.configure(video_config)
picam2.encode_stream_name = "raw"
encoder = Encoder()

picam2.start_recording(encoder, "test.raw", pts="timestamp.txt")
time.sleep(5)
picam2.stop_recording()

buf = open("test.raw", "rb").read(size[0] * size[1] * 2)
arr = np.frombuffer(buf, dtype=np.uint16).reshape((size[1], size[0]))

# Scale 10 bit / channel to 8 bit per channel
im = Image.fromarray((arr * ((2**8 - 1) / (2**10 - 1))).astype(np.uint8))
im.save("test-8bit.tif")

# Note - this will look very dark, because it's 10 bit colour depth of image, in
# a 16 bit / channel tiff
im2 = Image.fromarray(arr)
im2.save("test-16bit.tif")

# Create DNG file from frame, based on https://github.com/schoolpost/PiDNG/blob/master/examples/raw2dng.py
# Tested loading of DNG in darktable
r = RAW2DNG()
t = DNGTags()
bpp = 10
t.set(Tag.ImageWidth, size[0])
t.set(Tag.ImageLength, size[1])
t.set(Tag.TileWidth, size[0])
t.set(Tag.TileLength, size[1])
t.set(Tag.Orientation, Orientation.Horizontal)
t.set(Tag.PhotometricInterpretation, PhotometricInterpretation.Color_Filter_Array)
t.set(Tag.SamplesPerPixel, 1)
t.set(Tag.BitsPerSample, bpp)
t.set(Tag.CFARepeatPatternDim, [2, 2])
t.set(Tag.CFAPattern, CFAPattern.GBRG)
t.set(Tag.DNGVersion, DNGVersion.V1_4)
t.set(Tag.DNGBackwardVersion, DNGVersion.V1_2)
r.options(t, path="", compress=False)
r.convert(arr, filename="test")

picam2.close()
