import argparse
import os
import multiprocessing
import queue
import threading

import cv2
import numpy as np

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


class Detection:
    def __init__(self, coords, category, conf, scaler_crop):
        """Create a Detection object, recording the bounding box, category and confidence."""
        self.category = category
        self.conf = conf
        # Scale the box to the output stream dimensions.
        isp_output_size = picam2.camera_configuration()['main']["size"]
        sensor_output_size = picam2.camera_configuration()["raw"]["size"]
        full_sensor_resolution = picam2.sensor_resolution
        obj_scaled = imx500.convert_inference_coords(
            coords,
            full_sensor_resolution,
            scaler_crop,
            isp_output_size,
            sensor_output_size,
        )
        self.box = (obj_scaled.x, obj_scaled.y, obj_scaled.width, obj_scaled.height)

    def __str__(self):
        return f'({self.box[0]}, {self.box[1]})/{self.box[2]}x{self.box[3]} - {LABELS[int(self.category)]} ({self.conf*100:.2f}%)'

    def __repr__(self):
        return self.__str__()


def parse_detections(output_tensor, scaler_crop):
    """Parse the output tensor into a number of detected objects, scaled to the ISP out."""
    # Wait for result from child processes in the order submitted.
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

    detections = [
        Detection(coords, category, conf, scaler_crop)
        for coords, category, conf in zip(zip(*coords_list), categories, confs)
        if conf > CONF_THRESHOLD
    ]
    return detections


def draw_detections(jobs):
    """Draw the detections for this request onto the ISP output."""
    # Wait for result from child processes in the order submitted.
    while (job := jobs.get()) is not None:
        request, async_result = job
        detections = async_result.get()
        with MappedArray(request, 'main') as m:
            for detection in detections:
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
            cv2.imshow('IMX500 Object Detection', m.array)
            cv2.waitKey(1)
        request.release()


with open("class80.txt", "r") as f:
    LABELS = f.read().split("\n")

if args.ignore_dash_labels:
    LABELS = [l for l in LABELS if l and l != "-"]

# This must be called before instantiation of Picamera2
imx500 = IVS.ivs.from_network_file(os.path.abspath(MODEL))

picam2 = Picamera2()
main = {'format': 'RGB888'}
config = picam2.create_preview_configuration(main, controls={"FrameRate": 30})
picam2.start(config, show_preview=False)

width = 0
height = 0

for _ in range(10):
    try:
        t = picam2.capture_metadata()["Imx500InputTensorInfo"]
        network_name, width, height, num_channels = imx500.get_input_tensor_info(t)
        break
    except KeyError:
        pass

for _ in range(10):
    try:
        t = picam2.capture_metadata()["Imx500OutputTensorInfo"]
        output_tensor_info = imx500.get_output_tensor_info(t)
        tensor_data_num = [i['tensor_data_num'] for i in output_tensor_info['info']]
        break
    except KeyError:
        pass

INPUT_TENSOR_SIZE = (height, width)

# Will not be needed once the input tensor is embedded in the network fpk
imx500.config['input_tensor_size'] = (width, height)
imx500.set_inference_aspect_ratio(imx500.config['input_tensor_size'], picam2.sensor_resolution)

cv2.startWindowThread()

pool = multiprocessing.Pool(processes=4)
jobs = queue.Queue()

thread = threading.Thread(target=draw_detections, args=(jobs,))
thread.start()

while True:
    # The request gets released by handle_results
    request = picam2.capture_request()
    output_tensor = request.get_metadata().get("Imx500OutputTensor")
    scaler_crop = request.get_metadata().get("ScalerCrop")
    if output_tensor and scaler_crop:
        async_result = pool.apply_async(parse_detections, (output_tensor, scaler_crop))
        jobs.put((request, async_result))
    else:
        request.release()
