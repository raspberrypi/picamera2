import argparse
import os
import time

import cv2
import numpy as np

from picamera2.imx500 import IMX500
from picamera2 import MappedArray, Picamera2

parser = argparse.ArgumentParser()
parser.add_argument("--model", type=str, required=True, help="Path of the model")
parser.add_argument("--bbox-normalization", action="store_true", help="Normalize bbox")
parser.add_argument("--swap-tensors", action="store_true", help="Swap tensor 1 and 2")
parser.add_argument("--threshold", type=float, default=0.55, help="Detection threshold")
parser.add_argument("--ignore-dash-labels", action="store_true", help="remove '-' labels ")

args = parser.parse_args()

MODEL = args.model
BBOX_NORMALIZATION = args.bbox_normalization
SWAP_TENSORS = args.swap_tensors
CONF_THRESHOLD = args.threshold

last_detections = []

with open("class80.txt", "r") as f:
    LABELS = f.read().split("\n")

if args.ignore_dash_labels:
    LABELS = [l for l in LABELS if l and l != "-"]

# This must be called before instantiation of Picamera2
imx500 = IMX500(os.path.abspath(MODEL))
imx500.set_inference_aspect_ratio(imx500.config['input_tensor_size'])

class Detection:
    def __init__(self, coords, category, conf, request, stream="main"):
        """Create a Detection object, recording the bounding box, category and confidence."""
        self.category = category
        self.conf = conf
        # Scale the box to the output stream dimensions.
        isp_output_size = request.picam2.camera_configuration()[stream]["size"]
        sensor_output_size = request.picam2.camera_configuration()["raw"]["size"]
        scaler_crop = request.get_metadata()["ScalerCrop"]
        obj_scaled = imx500.convert_inference_coords(
            coords,
            scaler_crop,
            isp_output_size,
            sensor_output_size,
        )
        self.box = (obj_scaled.x, obj_scaled.y, obj_scaled.width, obj_scaled.height)


def parse_and_draw_detections(request):
    """Analyse the detected objects in the output tensor and draw them on the main output image."""
    parse_detections(request)
    draw_detections(request)


def parse_detections(request, stream="main"):
    """Parse the output tensor into a number of detected objects, scaled to the ISP out."""
    output_tensor = request.get_metadata().get("CnnOutputTensor")
    if output_tensor:
        output_tensor_split = np.array_split(
            output_tensor, np.cumsum(tensor_data_num[:-1])
        )
        if BBOX_NORMALIZATION:
            coords_list = [
                coords / imx500.config['input_tensor']['height']
                for coords in np.array_split(output_tensor_split[0], 4)
            ]
        else:
            coords_list = np.array_split(output_tensor_split[0], 4)
        if SWAP_TENSORS:
            categories, confs = output_tensor_split[1], output_tensor_split[2]
        else:
            categories, confs = output_tensor_split[2], output_tensor_split[1]
        global last_detections
        last_detections = [
            Detection(coords, category, conf, request, stream)
            for coords, category, conf in zip(zip(*coords_list), categories, confs)
            if conf > CONF_THRESHOLD
        ]
    request.detections = last_detections


def draw_detections(request, stream="main"):
    """Draw the detections for this request onto the ISP output."""
    with MappedArray(request, stream) as m:
        for detection in request.detections:
            x, y, w, h = detection.box
            label = f"{LABELS[int(detection.category)]} ({round(detection.conf, 2)})"
            cv2.putText(
                m.array,
                label,
                (x + 5, y + 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
            )
            cv2.rectangle(m.array, (x, y), (x + w, y + h), (0, 255, 0, 0))


picam2 = Picamera2()
config = picam2.create_preview_configuration(controls={"FrameRate": 30})
picam2.start(config, show_preview=True)

for _ in range(10):
    try:
        t = picam2.capture_metadata()["CnnOutputTensorInfo"]
        output_tensor_info = imx500.get_output_tensor_info(t)
        tensor_data_num = [i['tensor_data_num'] for i in output_tensor_info['info']]
        break
    except KeyError:
        pass

picam2.pre_callback = parse_and_draw_detections

while True:
    time.sleep(0.5)
