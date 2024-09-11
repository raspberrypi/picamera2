"""
Check model performance in specific configuration
Best for debug and deep dive
"""
import argparse
import cv2
import time

from debug_utils import debug_fps
from picamera2 import Picamera2, CompletedRequest
from picamera2.devices import IMX500

parser = argparse.ArgumentParser()
parser.add_argument("--model", type=str, required=True, help="Path of the model")
parser.add_argument("--fps", type=int, required=True, help="Camera per second")
parser.add_argument("-p", "--preview", action="store_true", help="show preview window")
parser.add_argument("-bu", "--buffer_count", type=int, default=16, help="set buffer count")
parser.add_argument("--check_input", action="store_true", help="check input")
parser.add_argument("--kpi", action="store_true", help="show dnn and dsp runtime")
parser.add_argument("-v", "--verbose", action="store_true", help="set verbose mode")
parser.add_argument("-r", "--preserve-aspect-ratio", action="store_true",
                    help="preprocess the image with  preserve aspect ratio")
parser.add_argument("--loop", action="store_true", help="use loop instead of preprocess_callback")
parser.add_argument("--skip-metadata", action="store_true", help="don't call get_metadata func")
args = parser.parse_args()

MODEL = args.model
CAM_FPS = args.fps
SHOW_PREVIEW = args.preview


def preprocess_callback(request: CompletedRequest):
    debug_fps(request, imx500, check_input=args.check_input, verbose=args.verbose, kpi=args.kpi,
              skip_metadata=args.skip_metadata)


# This must be called before instantiation of Picamera2
imx500 = IMX500(args.model)

start_init = time.time()
picam2 = Picamera2()
config = picam2.create_preview_configuration(controls={"FrameRate": args.fps}, buffer_count=args.buffer_count)
picam2.start(config, show_preview=SHOW_PREVIEW)
end_init = time.time()
print(f"init time: {end_init - start_init:.2f} sec")
if args.preserve_aspect_ratio:
    imx500.set_auto_aspect_ratio()

if not args.loop:
    picam2.pre_callback = preprocess_callback

print("FPS: frames per sec (camera), DFS: detections per sec (dnn), IPS: input tensors per sec (input consistency)")
print(f"Model: {MODEL}")
print(f"User define FPS:{args.fps}")
print(f"preview: {SHOW_PREVIEW}")

cv2.startWindowThread()

while True:
    if args.loop:
        r = picam2.capture_request()
        preprocess_callback(r)
        r.release()
    else:
        time.sleep(0.5)
