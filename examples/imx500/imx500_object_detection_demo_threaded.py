import argparse
import os
import queue
import threading

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
imx500 = IMX500.from_network_file(os.path.abspath(MODEL))

class Detection:
    def __init__(self, coords, category, conf, scaler_crop):
        """Create a Detection object, recording the bounding box, category and confidence."""
        self.category = category
        self.conf = conf
        # Scale the box to the output stream dimensions.
        isp_output_size = picam2.camera_configuration()['main']["size"]
        sensor_output_size = picam2.camera_configuration()["raw"]["size"]
        obj_scaled = imx500.convert_inference_coords(
            coords,
            scaler_crop,
            isp_output_size,
            sensor_output_size,
        )
        self.box = (obj_scaled.x, obj_scaled.y, obj_scaled.width, obj_scaled.height)


def parse_detections(metadata):
    """Parse the output tensor into a number of detected objects, scaled to the ISP out."""
    output_tensor = metadata.get("CnnOutputTensor")
    if output_tensor:
        output_tensor_split = np.array_split(
            output_tensor, np.cumsum(tensor_data_num[:-1])
        )
        if BBOX_NORMALIZATION:
            coords_list = [
                coords / INPUT_TENSOR_SIZE[0]
                for coords in np.array_split(output_tensor_split[0], 4)
            ]
        else:
            coords_list = np.array_split(output_tensor_split[0], 4)
        if SWAP_TENSORS:
            categories, confs = output_tensor_split[1], output_tensor_split[2]
        else:
            categories, confs = output_tensor_split[2], output_tensor_split[1]

        scaler_crop = metadata.get("ScalerCrop")
        detections = [
            Detection(coords, category, conf, scaler_crop)
            for coords, category, conf in zip(zip(*coords_list), categories, confs)
            if conf > CONF_THRESHOLD
        ]
    return detections


def draw_detections(request):
    """Draw the detections for this request onto the ISP output."""
    with MappedArray(request, "main") as m:
        for detection in last_detections:
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

width = 0
height = 0

for _ in range(10):
    try:
        t = picam2.capture_metadata()["CnnInputTensorInfo"]
        network_name, width, height, num_channels = imx500.get_input_tensor_info(t)
        break
    except KeyError:
        pass

for _ in range(10):
    try:
        t = picam2.capture_metadata()["CnnOutputTensorInfo"]
        output_tensor_info = imx500.get_output_tensor_info(t)
        tensor_data_num = [i['tensor_data_num'] for i in output_tensor_info['info']]
        break
    except KeyError:
        pass

INPUT_TENSOR_SIZE = (height, width)

# Will not be needed once the input tensor is embedded in the network fpk
imx500.config['input_tensor_size'] = (width, height)
imx500.set_inference_aspect_ratio(imx500.config['input_tensor_size'], picam2.sensor_resolution)

picam2.pre_callback = draw_detections

cv2.startWindowThread()

queue = queue.Queue()

def do_parsing(queue):
    global last_detections
    while True:
        output_tensor = queue.get()
        if output_tensor is None:
            break
        last_detections = parse_detections(output_tensor)

thread = threading.Thread(target=do_parsing, args=(queue,))
thread.start()

while True:
    try:
        metadata = picam2.capture_metadata()
        if queue.empty() and metadata.get("CnnOutputTensor"):
            queue.put(metadata)
        input_tensor = metadata["CnnInputTensor"]
        if INPUT_TENSOR_SIZE != (0, 0):
            cv2.imshow(
                "Input Tensor",
                imx500.input_tensor_image(input_tensor)
            )
            cv2.resizeWindow("Input Tensor", *INPUT_TENSOR_SIZE)
    except KeyError:
        pass
