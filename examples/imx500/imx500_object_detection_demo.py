import argparse
import os
import struct

import cv2
import numpy as np
from libcamera import Rectangle, Size

import picamera2.sony_ivs as IVS
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


class Detection:
    def __init__(self, coords, category, conf, request, stream="main"):
        """Create a Detection object, recording the bounding box, category and confidence."""
        self.category = category
        self.conf = conf
        # Scale the box to the output stream dimensions.
        isp_output_size = Size(*request.picam2.camera_configuration()[stream]["size"])
        sensor_output_size = Size(*request.picam2.camera_configuration()["raw"]["size"])
        full_sensor_resolution = Rectangle(
            *request.picam2.camera_properties["ScalerCropMaximum"]
        )
        scaler_crop = Rectangle(*request.get_metadata()["ScalerCrop"])
        obj_scaled = IVS.convert_inference_coords(
            coords,
            full_sensor_resolution,
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
    output_tensor = request.get_metadata().get("Imx500OutputTensor")
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


# This must be called before instantiation of Picamera2
IVS.set_network_firmware(os.path.abspath(MODEL))

picam2 = Picamera2()
config = picam2.create_preview_configuration(controls={"FrameRate": 30})
picam2.start(config, show_preview=True)

width = 0
height = 0

for _ in range(10):
    try:
        input_tensor_info = picam2.capture_metadata()["Imx500InputTensorInfo"]
        network_name, width, height, num_channels = struct.unpack(
            "64sIII", bytes(input_tensor_info)
        )
        network_name = network_name.decode("utf-8").rstrip("\x00")
        break
    except KeyError:
        pass

for _ in range(10):
    try:
        output_tensor_info = picam2.capture_metadata()["Imx500OutputTensorInfo"]
        network_name, *tensor_data_num, num_tensors = struct.unpack(
            "64s16II", bytes(output_tensor_info)
        )
        tensor_data_num = tensor_data_num[:num_tensors]
        break
    except KeyError:
        pass

INPUT_TENSOR_SIZE = (height, width)

picam2.pre_callback = parse_and_draw_detections

cv2.startWindowThread()

while True:
    try:
        input_tensor = picam2.capture_metadata()["Imx500InputTensor"]
        if INPUT_TENSOR_SIZE != (0, 0):
            cv2.imshow(
                "Input Tensor",
                IVS.input_tensor_image(
                    input_tensor, INPUT_TENSOR_SIZE, (384, 384, 384), (0, 0, 0)
                ),
            )
            cv2.resizeWindow("Input Tensor", *INPUT_TENSOR_SIZE)
    except KeyError:
        pass
